// TURNIK AI — tortilish mantig'i (Python versiyasining aynan nusxasi: settings + validation + bar + pullup_counter)
export const CFG = {
  minVisibility: 0.5, smoothAlpha: 0.55,
  chinOffsetRatio: 0.33, barTopOffset: 0.10, topFrames: 3, topHysteresis: 0.04,
  armsExtendedAngle: 150, pullStartAngle: 140, attemptAngle: 115, phaseFrames: 3,
  kneeBentAngle: 155, kneeBentFrames: 6, kneeMinCoverage: 0.5,
  bottomMaxSeconds: 3.0,
  thumbWrongFrames: 5, thumbRequired: false,
  lostHoldSeconds: 0.6, lostResetSeconds: 2.0,
};

export const LM = {
  NOSE: 0, MOUTH_L: 9, MOUTH_R: 10, EAR_L: 7, EAR_R: 8,
  SHOULDER_L: 11, SHOULDER_R: 12, ELBOW_L: 13, ELBOW_R: 14, WRIST_L: 15, WRIST_R: 16,
  PINKY_L: 17, PINKY_R: 18, INDEX_L: 19, INDEX_R: 20, THUMB_L: 21, THUMB_R: 22,
  HIP_L: 23, HIP_R: 24, KNEE_L: 25, KNEE_R: 26, ANKLE_L: 27, ANKLE_R: 28,
};
export const EDGES = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],
  [23,25],[25,27],[24,26],[26,28],[15,19],[16,20]];

export const OK = 'ok', WRONG = 'wrong', UNKNOWN = 'unknown';
export const ERR = {
  CHIN: "Jag'ingiz turnikdan to'liq o'tmadi.",
  KNEE_R: "O'ng tizzangiz bukildi.",
  KNEE_L: "Chap tizzangiz bukildi.",
  BOTTOM: "Pastki holatda 3 sekunddan ortiq turdingiz.",
  THUMB: "Bosh barmoq holati noto'g'ri.",
  THUMB_UNKNOWN: "Bosh barmoq holatini aniqlab bo'lmadi.",
  CYCLE: "To'liq tortilish sikli bajarilmadi (qo'llar to'liq cho'zilmadi).",
};

export function angle3(a, b, c) {
  const v1 = [a[0]-b[0], a[1]-b[1], a[2]-b[2]], v2 = [c[0]-b[0], c[1]-b[1], c[2]-b[2]];
  const n1 = Math.hypot(...v1), n2 = Math.hypot(...v2);
  if (n1 < 1e-6 || n2 < 1e-6) return null;
  const cos = Math.max(-1, Math.min(1, (v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]) / (n1*n2)));
  return Math.acos(cos) * 180 / Math.PI;
}

export function newMetrics(t = 0) {
  return { t, tracked: false, elbowAngle: null, chinY: null, handsY: null, scale: null,
           kneeR: null, kneeL: null, thumbR: UNKNOWN, thumbL: UNKNOWN };
}

const p3 = (p) => [p.x, p.y, p.z ?? 0];
const visOk = (lm, idx, thr) => idx.every(i => (lm[i].visibility ?? 0) >= thr);

// lm: [{x,y,z,visibility}] (33), world: [{x,y,z}] (33) yoki null
export function computeMetrics(lm, world, t, cfg = CFG) {
  const m = newMetrics(t);
  if (!lm) return m;
  const thr = cfg.minVisibility;
  const upper = [LM.SHOULDER_L, LM.SHOULDER_R, LM.ELBOW_L, LM.ELBOW_R, LM.WRIST_L, LM.WRIST_R];
  if (!visOk(lm, upper, thr)) return m;
  m.tracked = true;
  m.scale = Math.hypot(lm[LM.SHOULDER_L].x - lm[LM.SHOULDER_R].x, lm[LM.SHOULDER_L].y - lm[LM.SHOULDER_R].y);
  const src = (i) => world ? p3(world[i]) : p3(lm[i]);
  const angs = [];
  for (const [s, e, w] of [[LM.SHOULDER_L, LM.ELBOW_L, LM.WRIST_L], [LM.SHOULDER_R, LM.ELBOW_R, LM.WRIST_R]]) {
    const a = angle3(src(s), src(e), src(w));
    if (a !== null) angs.push(a);
  }
  m.elbowAngle = angs.length ? angs.reduce((x, y) => x + y) / angs.length : null;
  const hp = [LM.WRIST_L, LM.WRIST_R, LM.INDEX_L, LM.INDEX_R, LM.PINKY_L, LM.PINKY_R]
    .filter(i => lm[i].visibility >= thr).map(i => lm[i].y);
  if (hp.length) m.handsY = hp.reduce((x, y) => x + y) / hp.length;
  m.chinY = chinYEstimate(lm, thr, cfg.chinOffsetRatio);
  const knee = (h, k, a) => visOk(lm, [h, k, a], thr) ? angle3(src(h), src(k), src(a)) : null;
  m.kneeR = knee(LM.HIP_R, LM.KNEE_R, LM.ANKLE_R);
  m.kneeL = knee(LM.HIP_L, LM.KNEE_L, LM.ANKLE_L);
  return m;
}

// Jag' pastki nuqtasi modelda yo'q -> og'iz + (quloqlar masofasi * ratio) bilan BAHOLANADI
export function chinYEstimate(lm, thr, ratio) {
  if (!visOk(lm, [LM.MOUTH_L, LM.MOUTH_R, LM.EAR_L, LM.EAR_R], thr * 0.8)) return null;
  const mouthY = (lm[LM.MOUTH_L].y + lm[LM.MOUTH_R].y) / 2;
  const earD = Math.hypot(lm[LM.EAR_L].x - lm[LM.EAR_R].x, lm[LM.EAR_L].y - lm[LM.EAR_R].y);
  return mouthY + ratio * earD;
}

export class BarTracker {
  constructor(cfg = CFG) { this.cfg = cfg; this.reset(); }
  reset() { this.samples = []; this.centerY = null; this.locked = false; this.manualShift = 0; this.scale = 0.2; }
  unlock() { this.samples = []; this.locked = false; }
  update(handsY, elbow, scale) {
    if (scale) this.scale = scale;
    if (this.locked || handsY == null || elbow == null) return;
    if (elbow < this.cfg.armsExtendedAngle) { this.samples = []; return; }
    this.samples.push(handsY);
    if (this.samples.length > 45) this.samples.shift();
    if (this.samples.length >= 20) {
      const s = [...this.samples].sort((a, b) => a - b);
      this.centerY = (s.length % 2) ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
      const mean = this.samples.reduce((a, b) => a + b) / this.samples.length;
      const std = Math.sqrt(this.samples.reduce((a, b) => a + (b - mean) ** 2, 0) / this.samples.length);
      if (std < 0.01) this.locked = true;
    }
  }
  get ready() { return this.centerY !== null && this.locked; }
  get topY() {
    return this.centerY === null ? null : this.centerY - (this.cfg.barTopOffset + this.manualShift) * this.scale;
  }
  nudge(d) { this.manualShift += d; }
}

export const READY = 'READY', PULLING = 'PULLING', TOP = 'TOP', DESCENDING = 'DESCENDING',
  BOTTOM = 'BOTTOM', VALIDATION = 'VALIDATION';

const newCycle = (minElbow = 999, reachedTop = false) => ({
  minElbow, reachedTop, frames: 0,
  kneeTotal: { r: 0, l: 0 }, kneeSeen: { r: 0, l: 0 }, kneeRun: { r: 0, l: 0 }, kneeBent: { r: false, l: false },
  thumbWrong: { r: 0, l: 0 }, thumbSeen: { r: 0, l: 0 },
});

export class PullUpCounter {
  constructor(cfg = CFG, onEvent = () => {}) {
    this.cfg = cfg; this.onEvent = onEvent; this.bar = new BarTracker(cfg); this.reset();
  }
  reset(keepBar = false) {
    this.state = READY; this.total = 0; this.correct = 0; this.wrong = 0;
    this.verdicts = []; this.errorStats = {};
    this.bottomSince = null; this.bottomSeconds = 0; this.pending = null;
    this.cycle = newCycle(); this.counts = { pull: 0, top: 0, down: 0, ext: 0 };
    this.lastGoodT = null; this.chinRel = null; this.lastErrors = [];
    if (!keepBar) this.bar.reset();
  }
  bump(key, cond) { this.counts[key] = cond ? this.counts[key] + 1 : 0; return this.counts[key]; }

  update(m) {
    const cfg = this.cfg;
    if (!m.tracked || m.elbowAngle == null) {
      if (this.lastGoodT !== null && m.t - this.lastGoodT > cfg.lostResetSeconds) this.abortCycle();
      this.tickBottom(m.t);
      return this.state;
    }
    this.lastGoodT = m.t;
    this.bar.update(m.handsY, m.elbowAngle, m.scale);
    const topY = this.bar.topY;
    this.chinRel = (this.bar.ready && m.chinY != null && m.scale) ? (topY - m.chinY) / m.scale : null;
    const elbow = m.elbowAngle, n = cfg.phaseFrames, cyc = this.cycle;
    cyc.frames++; cyc.minElbow = Math.min(cyc.minElbow, elbow);
    this.trackKnees(m); this.trackThumbs(m);

    const extended = this.bump('ext', elbow >= cfg.armsExtendedAngle);
    const topNow = this.bump('top', this.chinRel !== null && this.chinRel >= 0);
    const downNow = this.bump('down', this.chinRel !== null && this.chinRel < -cfg.topHysteresis);
    const pullNow = this.bump('pull', elbow < cfg.pullStartAngle);

    if (this.state === READY || this.state === BOTTOM) {
      if (this.bar.ready && pullNow >= n) this.beginPull(m.t);
    } else if (this.state === PULLING) {
      if (topNow >= n) { this.state = TOP; cyc.reachedTop = true; }
      else if (extended >= n + 2) {
        if (cyc.minElbow < cfg.attemptAngle) this.finalize(m.t, false, true); else this.cycle = newCycle();
        this.state = READY;
      }
    } else if (this.state === TOP) {
      if (downNow >= n) this.state = DESCENDING;
    } else if (this.state === DESCENDING) {
      if (extended >= n) this.enterBottom(m.t);
      else if (topNow >= n) {
        this.finalize(m.t, true, false);
        this.state = TOP; this.cycle = newCycle(elbow, true);
      }
    }
    this.tickBottom(m.t);
    return this.state;
  }

  beginPull(t) {
    if (this.state === BOTTOM) this.resolvePending(t);
    this.bottomSince = null; this.bottomSeconds = 0; this.cycle = newCycle(); this.state = PULLING;
  }
  trackKnees(m) {
    const c = this.cycle, cfg = this.cfg;
    for (const [side, ang] of [['r', m.kneeR], ['l', m.kneeL]]) {
      c.kneeTotal[side]++;
      if (ang == null) { c.kneeRun[side] = 0; continue; }
      c.kneeSeen[side]++;
      if (ang < cfg.kneeBentAngle) { if (++c.kneeRun[side] >= cfg.kneeBentFrames) c.kneeBent[side] = true; }
      else c.kneeRun[side] = 0;
    }
  }
  trackThumbs(m) {
    const c = this.cycle;
    for (const [side, st] of [['r', m.thumbR], ['l', m.thumbL]]) {
      if (st === UNKNOWN) continue;
      c.thumbSeen[side]++;
      if (st === WRONG) c.thumbWrong[side]++;
    }
  }
  enterBottom(t) {
    this.state = BOTTOM; this.bottomSince = t; this.bottomSeconds = 0;
    this.pending = this.finalize(t, true, true);
  }
  tickBottom(t) {
    if (this.state === BOTTOM && this.bottomSince !== null) {
      this.bottomSeconds = t - this.bottomSince;
      if (this.pending && this.bottomSeconds > this.cfg.bottomMaxSeconds) {
        this.reviseForBottom(this.pending, this.bottomSeconds); this.pending = null;
      }
    }
  }
  resolvePending(t) {
    if (this.pending) { this.pending.bottomSeconds = Math.max(0, t - (this.bottomSince ?? t)); this.pending = null; }
  }
  reviseForBottom(v, secs) {
    v.bottom = WRONG; v.bottomSeconds = secs;
    if (!v.errors.includes(ERR.BOTTOM)) {
      const wasValid = v.errors.length === 0;
      v.errors.push(ERR.BOTTOM);
      this.errorStats[ERR.BOTTOM] = (this.errorStats[ERR.BOTTOM] || 0) + 1;
      if (wasValid) { this.correct--; this.wrong++; }
    }
    this.lastErrors = [...v.errors];
    this.onEvent('rep_revised', v);
  }
  abortCycle() { this.cycle = newCycle(); this.pending = null; this.bottomSince = null; this.state = READY; }
  kneeStatus(side) {
    const c = this.cycle;
    if (c.kneeBent[side]) return WRONG;
    if (c.kneeTotal[side] && c.kneeSeen[side] / c.kneeTotal[side] >= this.cfg.kneeMinCoverage) return OK;
    return UNKNOWN;
  }
  thumbStatus() {
    const c = this.cycle;
    if (['r', 'l'].some(s => c.thumbWrong[s] >= this.cfg.thumbWrongFrames)) return WRONG;
    return UNKNOWN; // frontal kamerada "to'g'ri" deb tasdiqlab bo'lmaydi
  }
  finalize(t, reachedTop, descentComplete) {
    const c = this.cycle, cfg = this.cfg;
    const v = { index: this.total + 1, minElbow: c.minElbow < 999 ? c.minElbow : null,
      chin: reachedTop ? OK : WRONG, kneeR: this.kneeStatus('r'), kneeL: this.kneeStatus('l'),
      thumb: this.thumbStatus(), bottom: OK, complete: descentComplete, bottomSeconds: 0, errors: [], notes: [] };
    if (!reachedTop) v.errors.push(ERR.CHIN);
    if (v.kneeR === WRONG) v.errors.push(ERR.KNEE_R);
    if (v.kneeL === WRONG) v.errors.push(ERR.KNEE_L);
    if (v.thumb === WRONG) v.errors.push(ERR.THUMB);
    if (!descentComplete) v.errors.push(ERR.CYCLE);
    if (v.kneeR === UNKNOWN) v.notes.push("O'ng tizza tekshirib bo'lmadi");
    if (v.kneeL === UNKNOWN) v.notes.push("Chap tizza tekshirib bo'lmadi");
    if (v.thumb === UNKNOWN) {
      v.notes.push(ERR.THUMB_UNKNOWN);
      if (cfg.thumbRequired) v.errors.push(ERR.THUMB_UNKNOWN);
    }
    this.total++;
    if (v.errors.length === 0) this.correct++; else this.wrong++;
    for (const e of v.errors) this.errorStats[e] = (this.errorStats[e] || 0) + 1;
    this.verdicts.push(v); this.lastErrors = [...v.errors];
    this.cycle = newCycle();
    this.onEvent('rep', v);
    return v;
  }
  finish(t) { if (this.pending) this.resolvePending(t ?? this.bottomSince ?? 0); }
}

// ---- Bosh barmoq (hand landmarks): faqat ishonchli dalil bo'lsa WRONG ----
export function analyzeThumb(hand, barTopY, barCenterY) {
  if (!hand || barTopY == null || barCenterY == null || hand.score < 0.7) return UNKNOWN;
  const lm = hand.lm;
  const handSize = Math.hypot(lm[0].x - lm[9].x, lm[0].y - lm[9].y);
  if (handSize < 1e-3) return UNKNOWN;
  const tip = lm[4], ip = lm[3], idx = lm[5], margin = 0.25 * handSize;
  const above = tip.y < barTopY - margin && ip.y < barTopY - margin;
  const nearIndex = Math.abs(tip.x - idx.x) < 0.9 * handSize;
  return (above && nearIndex) ? WRONG : UNKNOWN;
}
export function matchHandToWrist(hands, wrist, maxDist = 0.12) {
  let best = null, bd = maxDist;
  for (const h of hands) {
    const d = Math.hypot(h.lm[0].x - wrist.x, h.lm[0].y - wrist.y);
    if (d < bd) { best = h; bd = d; }
  }
  return best;
}
