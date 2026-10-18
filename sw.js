// Service worker del sistema (/sistema/). Red primero; si no hay internet, usa lo guardado.
const CACHE_NAME = 'sistema-0808-v3-1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  // Solo páginas y archivos estáticos; nunca la API (los datos siempre deben ser frescos)
  if (req.method !== 'GET' || new URL(req.url).pathname.startsWith('/api/')) return;
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copia = res.clone();
        caches.open(CACHE_NAME).then((c) => c.put(req, copia));
        return res;
      })
      .catch(() => caches.match(req))
  );
});
