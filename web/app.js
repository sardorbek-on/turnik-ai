// TURNIK AI — brauzer ilovasi: kamera + MediaPipe (pose/qo'l) + qoidalar + interfeys
import { PoseLandmarker, HandLandmarker, FilesetResolver } from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/vision_bundle.mjs';
import { CFG, LM, EDGES, PullUpCounter, computeMetrics, analyzeThumb, matchHandToWrist, UNKNOWN, ERR } from './counter.js';

const WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm';
const $ = (id) => document.getElementById(id);
const view = $('view'), ctx = view.getContext('2d'), video = $('cam');

const STATE_UZ = { READY: 'READY — tayyor', PULLING: 'PULLING — tortilmoqda', TOP: 'TOP — yuqorida',
  DESCENDING: 'DESCENDING — tushmoqda', BOTTOM: 'BOTTOM — pastda', VALIDATION: 'VALIDATION' };

const S = { pose: null, hands: null, stream: null, counting: false, paused: false, mirror: true, sound: true,
  facing: 'user', startedAt: null, frameNo: 0, lastVideoTime: -1, prevLm: null, hands2: [], thumb: { r: UNKNOWN, l: UNKNOWN },
  thumbAge: { r: 99, l: 99 }, fps: 0, fpsN: 0, fpsT: performance.now(), wake: null, running: false, lastCounts: [0, 0, 0] };

const counter = new PullUpCounter(CFG, onEvent);

// ---------------------------------------------------------------- AI modellari
async function loadModels() {
  const fileset = await FilesetResolver.forVisionTasks(WASM);
  const make = async (Cls, model, extra) => {
    for (const delegate of ['GPU', 'CPU']) {
      try {
        return await Cls.createFromOptions(fileset, { baseOptions: { modelAssetPath: model, delegate }, runningMode: 'VIDEO', ...extra });
      } catch (e) { console.warn(Cls.name, delegate, 'ishlamadi:', e); }
    }
    throw new Error('Model yuklanmadi: ' + model);
  };
  S.pose = await make(PoseLandmarker, './models/pose_landmarker_full.task',
    { numPoses: 1, minPoseDetectionConfidence: .5, minPosePresenceConfidence: .5, minTrackingConfidence: .5 });
  S.hands = await make(HandLandmarker, './models/hand_landmarker.task',
    { numHands: 2, minHandDetectionConfidence: .5, minHandPresenceConfidence: .5, minTrackingConfidence: .5 });
}

// ---------------------------------------------------------------- kamera
async function startCamera() {
  stopCamera();
  const [w, h] = $('selRes').value.split('x').map(Number);
  const devId = $('selCam').value;
  const video_c = { width: { ideal: w }, height: { ideal: h }, frameRate: { ideal: 30 } };
  if (devId) video_c.deviceId = { exact: devId }; else video_c.facingMode = S.facing;
  try {
    S.stream = await navigator.mediaDevices.getUserMedia({ video: video_c, audio: false });
  } catch (e) {
    alert('Kamerani ochib bo\'lmadi: ' + e.name + '. Brauzerda kameraga ruxsat bering. Sayt HTTPS (yoki localhost) bo\'lishi shart.');
    return false;
  }
  video.srcObject = S.stream;
  await video.play();
  const track = S.stream.getVideoTracks()[0];
  S.facing = (track.getSettings().facingMode) || S.facing;
  S.mirror = S.facing !== 'environment' && !/back|orqa/i.test(track.label);
  applyMirror();
  await fillCameras(track.getSettings().deviceId);
  $('placeholder').hidden = true; $('hud').hidden = false;
  $('btnStart').disabled = false;
  $('btnCam').textContent = 'Kamerani yoqish';
  if (!S.running) { S.running = true; requestAnimationFrame(loop); }
  return true;
}
function stopCamera() {
  if (S.stream) S.stream.getTracks().forEach(t => t.stop());
  S.stream = null; S.lastVideoTime = -1;
}
async function fillCameras(current) {
  const devs = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'videoinput');
  $('selCam').innerHTML = devs.map((d, i) => `<option value="${d.deviceId}">${d.label || 'Kamera ' + (i + 1)}</option>`).join('');
  if (current) $('selCam').value = current;
}
function applyMirror() {
  view.classList.toggle('mirror', S.mirror);
  $('btnMirror').textContent = "Ko'zgu: " + (S.mirror ? 'yoqilgan' : "o'chirilgan");
}

// ---------------------------------------------------------------- asosiy sikl
function loop() {
  requestAnimationFrame(loop);
  if (!S.stream || video.readyState < 2 || video.currentTime === S.lastVideoTime) return;
  S.lastVideoTime = video.currentTime;
  const vw = video.videoWidth, vh = video.videoHeight;
  if (view.width !== vw || view.height !== vh) { view.width = vw; view.height = vh; }
  ctx.drawImage(video, 0, 0, vw, vh);
  if (S.paused) return;

  const now = performance.now(), t = now / 1000;
  S.frameNo++;
  let lm = null, world = null;
  try {
    const res = S.pose.detectForVideo(video, now);
    if (res.landmarks && res.landmarks.length) {
      lm = res.landmarks[0].map(p => ({ x: p.x, y: p.y, z: p.z, visibility: p.visibility ?? 0 }));
      world = res.worldLandmarks[0];
      if (S.prevLm) for (let i = 0; i < lm.length; i++) {          // EMA silliqlash
        const a = CFG.smoothAlpha, q = S.prevLm[i];
        lm[i].x = a * lm[i].x + (1 - a) * q.x; lm[i].y = a * lm[i].y + (1 - a) * q.y; lm[i].z = a * lm[i].z + (1 - a) * q.z;
      }
      S.prevLm = lm.map(p => ({ ...p }));
    } else S.prevLm = null;
  } catch (e) { console.error('pose xato', e); }

  const m = computeMetrics(lm, world, t, CFG);
  const bar = counter.bar;

  // Bosh barmoq: har 2-kadrda, faqat turnik aniq bo'lganda
  if (m.tracked && bar.ready && S.frameNo % 2 === 0) {
    try {
      const hr = S.hands.detectForVideo(video, now + 0.01);
      S.hands2 = hr.landmarks.map((l, i) => ({ lm: l, score: hr.handedness[i][0].score }));
    } catch (e) { S.hands2 = []; }
    for (const [side, w] of [['l', LM.WRIST_L], ['r', LM.WRIST_R]]) {
      const h = matchHandToWrist(S.hands2, lm[w]);
      S.thumb[side] = analyzeThumb(h, bar.topY, bar.centerY); S.thumbAge[side] = 0;
    }
  } else { S.thumbAge.l++; S.thumbAge.r++; }
  for (const s of ['l', 'r']) if (S.thumbAge[s] > 4) S.thumb[s] = UNKNOWN;
  m.thumbL = S.thumb.l; m.thumbR = S.thumb.r;

  if (S.counting) counter.update(m); else bar.update(m.handsY, m.elbowAngle, m.scale);

  draw(lm, m);
  updateHud(m);
  S.fpsN++;
  if (now - S.fpsT >= 700) { S.fps = S.fpsN * 1000 / (now - S.fpsT); S.fpsN = 0; S.fpsT = now; $('fps').textContent = `FPS ${S.fps.toFixed(0)}`; }
}

function draw(lm, m) {
  const w = view.width, h = view.height, bar = counter.bar;
  if (lm) {
    ctx.lineWidth = Math.max(3, w / 220); ctx.strokeStyle = '#a05bff'; ctx.lineCap = 'round';
    for (const [a, b] of EDGES) {
      if (lm[a].visibility >= CFG.minVisibility && lm[b].visibility >= CFG.minVisibility) {
        ctx.beginPath(); ctx.moveTo(lm[a].x * w, lm[a].y * h); ctx.lineTo(lm[b].x * w, lm[b].y * h); ctx.stroke();
      }
    }
    ctx.fillStyle = '#fff';
    for (let i = 11; i < 33; i++) if (lm[i].visibility >= CFG.minVisibility) {
      ctx.beginPath(); ctx.arc(lm[i].x * w, lm[i].y * h, Math.max(4, w / 180), 0, 7); ctx.fill();
    }
    if (m.chinY != null) {
      const cx = (lm[LM.MOUTH_L].x + lm[LM.MOUTH_R].x) / 2 * w, over = counter.chinRel !== null && counter.chinRel >= 0;
      ctx.fillStyle = over ? '#78e678' : '#50dcff';
      ctx.beginPath(); ctx.arc(cx, m.chinY * h, Math.max(6, w / 120), 0, 7); ctx.fill();
    }
  }
  if (bar.topY !== null) {
    const y = bar.topY * h;
    ctx.setLineDash([w / 40, w / 80]); ctx.lineWidth = Math.max(2, w / 300);
    ctx.strokeStyle = bar.ready ? '#50dcff' : '#a0a0a0';
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); ctx.setLineDash([]);
  }
}

function updateHud(m) {
  const c = counter, cur = [c.total, c.correct, c.wrong];
  [['sTotal', 0], ['sOk', 1], ['sBad', 2]].forEach(([id, i]) => {
    const el = $(id);
    if (String(cur[i]) !== el.textContent) {
      el.textContent = cur[i]; const box = el.parentElement; box.classList.add('pulse'); setTimeout(() => box.classList.remove('pulse'), 250);
    }
  });
  $('chip').textContent = STATE_UZ[S.counting ? c.state : 'READY'];
  const secs = c.state === 'BOTTOM' && S.counting ? c.bottomSeconds : 0;
  $('tVal').textContent = secs.toFixed(1);
  $('bottomTimer').classList.toggle('over', secs > CFG.bottomMaxSeconds);
  const bm = $('barMsg');
  bm.className = c.bar.ready ? 'ok' : '';
  bm.textContent = c.bar.ready ? 'Turnik aniqlandi ✓' : (!m.tracked
    ? "Odam to'liq ko'rinmayapti — qo'llar, tirsaklar, yelkalar kadrda bo'lsin"
    : "Turnik aniqlanmoqda — osilib, qo'llarni to'g'rilab 1–2 s turing");
  const errs = c.lastErrors, notes = c.verdicts.length ? c.verdicts[c.verdicts.length - 1].notes : [];
  const html = errs.map(e => `<div class="err">✗ ${e}</div>`).join('') + (!errs.length ? notes.map(n => `<div class="note">• ${n}</div>`).join('') : '');
  if ($('errors').dataset.k !== html) { $('errors').innerHTML = html; $('errors').dataset.k = html; }
}

// ---------------------------------------------------------------- hodisalar, ovoz
function beep(freq, dur = .15) {
  if (!S.sound) return;
  try {
    const a = beep.ctx || (beep.ctx = new (window.AudioContext || window.webkitAudioContext)());
    const o = a.createOscillator(), g = a.createGain();
    o.frequency.value = freq; g.gain.value = .15; o.connect(g); g.connect(a.destination);
    o.start(); o.stop(a.currentTime + dur);
  } catch { /* ovoz ixtiyoriy */ }
}
function onEvent(kind, v) {
  if (kind === 'rep') { beep(v.errors.length ? 220 : 880, v.errors.length ? .3 : .12); if (navigator.vibrate) navigator.vibrate(v.errors.length ? [80, 60, 80] : 40); }
  if (kind === 'rep_revised') beep(220, .3);
}

// ---------------------------------------------------------------- boshqaruv
async function start() {
  counter.reset(true); S.counting = true; S.paused = false; S.startedAt = Date.now();
  $('btnStart').disabled = true; $('btnPause').disabled = false; $('btnStop').disabled = false; $('btnPause').textContent = 'PAUSE';
  try { S.wake = await navigator.wakeLock?.request('screen'); } catch { /* ixtiyoriy */ }
}
function pause() { S.paused = !S.paused; $('btnPause').textContent = S.paused ? 'DAVOM ETISH' : 'PAUSE'; }
function stop() {
  if (!S.counting) return;
  counter.finish(performance.now() / 1000);
  S.counting = false; S.paused = false;
  const dur = (Date.now() - S.startedAt) / 1000;
  $('btnStart').disabled = false; $('btnPause').disabled = true; $('btnStop').disabled = true; $('btnPause').textContent = 'PAUSE';
  try { S.wake?.release(); } catch { /* */ }
  const data = { at: new Date(S.startedAt).toISOString(), duration: dur, total: counter.total, correct: counter.correct,
    wrong: counter.wrong, errorStats: { ...counter.errorStats }, notes: [...new Set(counter.verdicts.flatMap(v => v.notes))] };
  if (data.total > 0) saveHistory(data);
  showResult(data);
}

// ---------------------------------------------------------------- tarix va natijalar
const HKEY = 'turnik_ai_history';
const loadHistory = () => { try { return JSON.parse(localStorage.getItem(HKEY) || '[]'); } catch { return []; } };
function saveHistory(d) { try { const h = loadHistory(); h.unshift(d); localStorage.setItem(HKEY, JSON.stringify(h.slice(0, 200))); } catch { /* */ } }
const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

function showResult(d) {
  const pct = d.total ? Math.round(100 * d.correct / d.total) : 0;
  const errs = Object.entries(d.errorStats).sort((a, b) => b[1] - a[1]);
  $('resultBody').innerHTML = `<div class="res"><h2>Natijalar</h2>
    <div class="big">${d.correct}<span class="muted"> / ${d.total} to'g'ri</span></div>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <div class="line"><span>Jami tortilishlar</span><b>${d.total}</b></div>
    <div class="line"><span>To'g'ri</span><b style="color:var(--ok)">${d.correct}</b></div>
    <div class="line"><span>Noto'g'ri</span><b style="color:var(--bad)">${d.wrong}</b></div>
    <div class="line"><span>Muvaffaqiyat</span><b>${pct}%</b></div>
    <div class="line"><span>Davomiyligi</span><b>${mmss(d.duration)}</b></div>
    <p><b>Xatolar statistikasi</b></p>
    ${errs.length ? '<ul>' + errs.map(([e, n]) => `<li>${e} ×${n}</li>`).join('') + '</ul>' : '<p class="muted">Xato qayd etilmadi</p>'}
    ${d.notes.length ? '<p class="muted">Tekshirib bo\'lmaganlar (xato hisoblanmadi):<br>' + d.notes.join('<br>') + '</p>' : ''}
    </div><button class="primary wide" id="btnCloseRes">Yopish</button>`;
  $('result').hidden = false;
  $('btnCloseRes').onclick = () => { $('result').hidden = true; };
}
function renderHistory() {
  const h = loadHistory();
  $('tabHist').innerHTML = h.length
    ? `<table><tr><th>Sana</th><th>Vaqt</th><th>Jami</th><th>To'g'ri</th><th>%</th></tr>` + h.map(x =>
      `<tr><td>${new Date(x.at).toLocaleString('uz', { dateStyle: 'short', timeStyle: 'short' })}</td><td>${mmss(x.duration)}</td><td>${x.total}</td><td>${x.correct}</td><td>${x.total ? Math.round(100 * x.correct / x.total) : 0}%</td></tr>`).join('') + '</table>'
      + '<button id="btnClearHist">Tarixni tozalash</button>'
    : '<p class="hint">Hozircha mashg\'ulot yo\'q.</p>';
  const b = $('btnClearHist'); if (b) b.onclick = () => { if (confirm("Butun tarix o'chirilsinmi?")) { localStorage.removeItem(HKEY); renderHistory(); } };
}

// ---------------------------------------------------------------- UI ulash
$('btnCam').onclick = startCamera;
$('btnStart').onclick = start; $('btnPause').onclick = pause; $('btnStop').onclick = stop;
$('btnMenu').onclick = () => { $('sheet').hidden = false; };
$('btnCloseSheet').onclick = () => { $('sheet').hidden = true; };
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tabs button').forEach(x => x.classList.toggle('on', x === b));
  $('tabSet').hidden = b.dataset.tab !== 'set'; $('tabHist').hidden = b.dataset.tab !== 'hist';
  if (b.dataset.tab === 'hist') renderHistory();
});
$('selCam').onchange = startCamera; $('selRes').onchange = () => S.stream && startCamera();
$('btnFlip').onclick = () => { S.facing = S.facing === 'user' ? 'environment' : 'user'; $('selCam').innerHTML = ''; startCamera(); };
$('btnMirror').onclick = () => { S.mirror = !S.mirror; applyMirror(); };
$('btnSound').onclick = () => { S.sound = !S.sound; $('btnSound').textContent = 'Ovoz: ' + (S.sound ? 'yoqilgan' : "o'chirilgan"); };
$('btnRecal').onclick = () => counter.bar.unlock();
$('btnUp').onclick = () => counter.bar.nudge(0.05);
$('btnDown').onclick = () => counter.bar.nudge(-0.05);
document.addEventListener('visibilitychange', () => { if (document.hidden && S.counting && !S.paused) pause(); });

if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('sw.js').catch(() => {});

(async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    $('loadMsg').textContent = "Kamera ishlamaydi: sayt HTTPS orqali ochilishi kerak (yoki localhost).";
  }
  try {
    await loadModels();
    $('loadMsg').textContent = 'AI tayyor ✓';
    $('btnCam').disabled = !navigator.mediaDevices?.getUserMedia;
  } catch (e) {
    $('loadMsg').textContent = "AI modellarini yuklab bo'lmadi: " + e.message + " (internet kerak: MediaPipe fayllari CDN dan olinadi)";
    console.error(e);
  }
})();
window.__turnik = { S, counter, loop };   // sinov uchun
