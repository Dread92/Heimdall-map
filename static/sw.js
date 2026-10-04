// Heimdall — service worker: push notifications, and the what-to-do guide kept for when there is no network.
// Nothing live is ever cached: the guide (/guide) and the two files it draws with are the only answers this worker
// gives, and even those come from the network first — the stored copy is used only when the network fails.
const GUIDE_CACHE = 'heimdall-guide-1';
const GUIDE = ['/guide', '/static/glyphs.js', '/static/heimdall-64.png'];
self.addEventListener('install', e => {
  self.skipWaiting();
  // a failed download must not stop the worker (and the push notifications) from installing
  e.waitUntil(caches.open(GUIDE_CACHE).then(c => c.addAll(GUIDE)).catch(() => {}));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== self.location.origin || !GUIDE.includes(u.pathname)) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const copy = r.clone(); caches.open(GUIDE_CACHE).then(c => c.put(u.pathname, copy)).catch(() => {}); }
    return r;
  }).catch(() => caches.match(u.pathname).then(r => r || Response.error())));
});
// the page can ask the waiting worker to take over immediately (the "new version" bar does this)
self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('heimdall-guide-') && k !== GUIDE_CACHE).map(k => caches.delete(k))))
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
