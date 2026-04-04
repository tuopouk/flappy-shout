const CACHE = "ploply-bird-cache-v1";
const offlineFallbackPage = "/assets/offline.html";


const ASSETS_TO_CACHE = [
  offlineFallbackPage,
  "/assets/manifest.json",
  "/assets/images/android-launchericon-192-192.png",
  "/assets/images/android-launchericon-512-512.png",
  "/assets/images/android-launchericon-72-72.png",
  "/assets/images/android-launchericon-48-48.png",
  "/assets/images/android-launchericon-144-144.png",
  "/assets/images/android-launchericon-96-96.png"
];


self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => {
      console.log("[SW] Caching assets");
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});


self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))
    )
  );
  self.clients.claim();
});


self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);


  if (event.request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          return await fetch(event.request);
        } catch (error) {
          console.log("[SW] Network failed, serving offline page");
          const cache = await caches.open(CACHE);
          return await cache.match(offlineFallbackPage);
        }
      })()
    );
    return;
  }


  if (ASSETS_TO_CACHE.some(path => url.pathname.endsWith(path) || url.pathname === path)) {
    event.respondWith(
      caches.match(event.request).then(response => {
        return response || fetch(event.request);
      })
    );
    return;
  }

  // C. Kaikki muu (API-kutsut, Dashin sisäiset scriptit) -> Suoraan verkosta
  // Ei tehdä mitään, annetaan selaimen hoitaa.
});