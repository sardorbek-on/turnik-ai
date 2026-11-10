// Oflayn kesh: ilova fayllari, modellar va MediaPipe (CDN) birinchi yuklashdan keyin keshlanadi.
const CACHE = 'turnik-ai-v1';
const SHELL = ['./', 'index.html', 'style.css', 'app.js', 'counter.js', 'manifest.json', 'icon-192.png', 'icon-512.png',
  'models/pose_landmarker_full.task', 'models/hand_landmarker.task'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || !(u.origin === location.origin || u.hostname === 'cdn.jsdelivr.net')) return;
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
    return res;
  })));
});
