// Heimdall — service worker: push notifications, and the pages kept for when the server cannot be reached.
// Nothing live is ever cached. 1.41: besides the guide, the two pages and the files they are drawn with are kept,
// network first: the stored copy answers only when the network fails or the server answers 5xx (a restart, a
// deploy, an overloaded host) — so the app still opens and says it is reconnecting, instead of a browser error page.
// The data (/api/…) is never stored: an old alert status shown as current would be worse than none.
// 1.53: the satellite tiles and the map's drawing are kept too (below) — pictures and borders, never a status.
const CACHE = 'heimdall-shell-3';
// 1.53, the owner: "pre-load the satellite and the map on the phone so it opens quicker". The satellite tiles never
// change under the same address (the layer's version is in it), so they are kept here and answered from here first —
// the map opens with its picture at once and with no network; the ones of Kyiv and around are fetched ahead once per
// version (the page asks, see warmTiles). Esri's closer tiles are not kept here: the browser's own cache keeps them
// for as long as Esri's answer allows.
// 1.54.7: emptied once (-2): a tile kept wrong on a phone is fetched again
const TILES = 'heimdall-tiles-2';
const TILES_MAX = 5000;
// the map's drawing (borders, towns, districts): answered from here at once, then refreshed for the next opening
// 1.57: and the city's shelters (static/shelters.js), so the nearest one is still found with no network
const FAST = ['/static/kyiv-map.json', '/static/map-ua.json', '/static/ukraine-map.json', '/static/light-map.json', '/static/kyiv-districts.json', '/static/towns-ua.json',
  '/static/shelters.js', '/static/shelters.json'];
const GUIDE = ['/guide', '/static/glyphs.js', '/static/heimdall-64.png'];
// downloaded at install: small, and shared by both pages
const SHELL = ['/static/i18n.js', '/static/live.js', '/static/heimdall-192.png', '/static/logo-64.png'];
// kept when they are first fetched through the worker (never downloaded ahead: a Light reader on 2G does not need
// the full map) — the page itself from its next opening on
const KEEP = GUIDE.concat(SHELL, ['/m', '/light', '/static/kyiv-map.json', '/static/map-ua.json', '/static/ukraine-map.json', '/static/light-map.json', '/static/kyiv-districts.json', '/static/towns-ua.json', '/manifest.json', '/light.webmanifest']);
// the addresses that are the same page
const ALIAS = { '/': '/m', '/k': '/m', '/kyiv': '/m', '/l': '/light' };
self.addEventListener('install', e => {
  self.skipWaiting();
  // a failed download must not stop the worker (and the push notifications) from installing
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(GUIDE.concat(SHELL).map(u => c.add(u).catch(() => {})))).catch(() => {}));
});
async function tile(req) {
  const c = await caches.open(TILES);
  const hit = await c.match(req);
  if (hit) return hit;
  const r = await fetch(req);
  if (r.ok && /^image\//.test(r.headers.get('content-type') || '')) { c.put(req, r.clone()).then(trimSoon).catch(() => {}); }   // a picture, nothing else
  return r;
}
let trimT = null;
function trimSoon() { if (trimT) return; trimT = setTimeout(async () => { trimT = null;
  try { const c = await caches.open(TILES), ks = await c.keys(); for (const k of ks.slice(0, Math.max(0, ks.length - TILES_MAX))) await c.delete(k); } catch (_) {} }, 20000); }
async function fast(key, req) {
  const c = await caches.open(CACHE);
  const hit = await c.match(key);
  const net = fetch(req).then(r => { if (r.ok) c.put(key, r.clone()).catch(() => {}); return r; });
  if (hit) { net.catch(() => {}); return hit; }
  return net;
}
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== self.location.origin) return;
  if (u.pathname.startsWith('/tiles/sat/')) { e.respondWith(tile(e.request).catch(() => Response.error())); return; }
  const key = ALIAS[u.pathname] || u.pathname;
  if (FAST.includes(key)) { e.respondWith(fast(key, e.request).catch(() => Response.error())); return; }   // fast() answers from the kept copy
  if (!KEEP.includes(key)) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(key, copy)).catch(() => {}); return r; }
    if (r.status >= 500) return caches.match(key).then(c => c || r);
    return r;
  }).catch(() => caches.match(key).then(r => r || Response.error())));
});
// the page can ask the waiting worker to take over immediately (the "new version" bar does this); 1.53: and to fetch the
// satellite tiles of Kyiv and around ahead, a few at a time, those not kept yet
self.addEventListener('message', e => {
  if (e.data === 'skipWaiting') self.skipWaiting();
  if (e.data && Array.isArray(e.data.warm)) e.waitUntil((async () => {
    const c = await caches.open(TILES), list = e.data.warm.filter(u => typeof u === 'string' && u.startsWith('/tiles/sat/')).slice(0, 800);
    for (let i = 0; i < list.length; i += 4) await Promise.all(list.slice(i, i + 4).map(async u => {
      try { if (!(await c.match(u))) { const r = await fetch(u); if (r.ok && /^image\//.test(r.headers.get('content-type') || '')) await c.put(u, r); } } catch (_) {} }));
    trimSoon();
  })());
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('heimdall-') && k !== CACHE && k !== TILES).map(k => caches.delete(k))))
    .catch(() => {}).then(() => self.clients.claim()));
});

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { title: 'Heimdall', body: e.data && e.data.text() }; }
  const title = d.title || 'Heimdall';
  const opts = {
    body: d.body || '',
    icon: '/static/heimdall-192.png',
    badge: '/static/logo-hd-badge.png',   // white on transparent: Android draws a badge from its alpha alone
    tag: d.tag || 'alert',
    renotify: true,
    requireInteraction: d.tag === 'threat' || /🔴|🚀|MiG/.test(title),
    vibrate: d.tag === 'threat' || /🔴|🚀/.test(title) ? [300, 120, 300, 120, 600] : [150],
    timestamp: d.ts ? Date.parse(d.ts) : Date.now(),
    data: { url: d.url || '/m' }
  };
  e.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/m';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if ('focus' in c) { c.navigate && c.navigate(url); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
