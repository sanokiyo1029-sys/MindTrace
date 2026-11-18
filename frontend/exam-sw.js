/* CACHE and ASSETS are set by the Vite build. Only the public shell goes in CacheStorage. */
const STUDENT_PAGE = '/student';
const PREFIX = 'mindtrace-exam-shell-';

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(
    [STUDENT_PAGE, ...ASSETS].map(url => new Request(url, { cache: 'reload', credentials: 'omit' })),
  )));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith(PREFIX) && key !== CACHE)
    .map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (request.mode === 'navigate' && url.pathname === STUDENT_PAGE) {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.status < 500) return response;
      } catch { /* Offline: reopen the saved app shell. */ }
      return (await (await caches.open(CACHE)).match(STUDENT_PAGE)) || Response.error();
    })());
  } else if (ASSETS.has(url.pathname)) {
    event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(url.pathname)) || fetch(request)));
  }
});
