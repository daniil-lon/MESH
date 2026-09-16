const CACHE_NAME = 'mesh-pwa-v20';
const STATIC_CACHE = 'mesh-static-v20';
const API_CACHE = 'mesh-api-v2';

const staticUrls = [
  '/',
  '/index.html',
  '/css/style.min.css?v=20',
  '/js/app.js',
  '/js/auth.js',
  '/js/api.js',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(staticUrls))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== STATIC_CACHE && name !== API_CACHE)
          .map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  const sameOrigin = url.origin === location.origin;

  if (url.pathname.startsWith('/admin.html')) {
    event.respondWith(fetch(event.request).catch(() => caches.match('/index.html')));
    return;
  }

  if (sameOrigin && event.request.method === 'GET' && url.pathname.startsWith('/api/')) {
    event.respondWith(staleWhileRevalidate(event.request));
    return;
  }

  if (!sameOrigin || event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then(response => {
      if (response) return response;
      return fetch(event.request).then(networkResponse => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type === 'opaque') {
          return networkResponse;
        }
        const clone = networkResponse.clone();
        caches.open(STATIC_CACHE)
          .then(cache => cache.put(event.request, clone))
          .catch(() => {});
        return networkResponse;
      });
    }).catch(() => caches.match('/index.html'))
  );
});

async function staleWhileRevalidate(request) {
  const cache = await caches.open(API_CACHE);
  const cached = await cache.match(request);
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      cache.put(request, networkResponse.clone()).catch(() => {});
    }
    return networkResponse;
  } catch (e) {
    if (cached) return cached;
    return new Response(JSON.stringify({ detail: 'offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

self.addEventListener('push', event => {
  let data = { title: 'IT Москва Колледж', body: 'Новое обновление', url: '/' };
  try {
    if (event.data) data = event.data.json();
  } catch (e) {}

  const options = {
    body: data.body,
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: data.url || '/' },
    vibrate: [100, 50, 100]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url
    ? event.notification.data.url
    : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if ('focus' in client) {
          if (client.url === targetUrl) {
            return client.focus();
          }
          return client.navigate(targetUrl).then(c => c.focus());
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});