/* Phase dev SmartCard — neutralise tout cache PWA hérité. */
self.addEventListener("install", function (event) {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    Promise.all([
      self.clients.claim(),
      caches.keys().then(function (keys) {
        return Promise.all(keys.map(function (key) {
          return caches.delete(key);
        }));
      }),
    ])
  );
});
