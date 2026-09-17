const CACHE = 'gda-dev-v1';
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/','/index.html','/manifest.json']))));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request).then(res => {
    const copy = res.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); return res;
  }).catch(() => caches.match('/index.html'))));
});
