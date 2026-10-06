// Heimdall — service worker: push notifications, and the pages kept for when the server cannot be reached.
// Nothing live is ever cached. 1.41: besides the guide, the two pages and the files they are drawn with are kept,
// network first: the stored copy answers only when the network fails or the server answers 5xx (a restart, a
// deploy, an overloaded host) — so the app still opens and says it is reconnecting, instead of a browser error page.
// The data (/api/…) is never stored: an old alert status shown as current would be worse than none.
const CACHE = 'heimdall-shell-2';
const GUIDE = ['/guide', '/static/glyphs.js', '/static/heimdall-64.png'];
// downloaded at install: small, and shared by both pages
const SHELL = ['/static/i18n.js', '/static/live.js', '/static/heimdall-192.png', '/static/logo-64.png'];
// kept when they are first fetched through the worker (never downloaded ahead: a Light reader on 2G does not need
// the full map) — the page itself from its next opening on
const KEEP = GUIDE.concat(SHELL, ['/m', '/light', '/static/kyiv-map.json', '/static/ukraine-map.json', '/static/light-map.json', '/static/kyiv-districts.json', '/manifest.json', '/light.webmanifest']);
// the addresses that are the same page
const ALIAS = { '/': '/m', '/k': '/m', '/kyiv': '/m', '/l': '/light' };
self.addEventListener('install', e => {
  self.skipWaiting();
  // a failed download must not stop the worker (and the push notifications) from installing
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(GUIDE.concat(SHELL).map(u => c.add(u).catch(() => {})))).catch(() => {}));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== self.location.origin) return;
  const key = ALIAS[u.pathname] || u.pathname;
  if (!KEEP.includes(key)) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(key, copy)).catch(() => {}); return r; }
    if (r.status >= 500) return caches.match(key).then(c => c || r);
    return r;
  }).catch(() => caches.match(key).then(r => r || Response.error())));
});
// the page can ask the waiting worker to take over immediately (the "new version" bar does this)
self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('heimdall-') && k !== CACHE).map(k => caches.delete(k))))
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
