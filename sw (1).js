const CACHE_NAME = 'wattwise-v2';
const STATIC_ASSETS = [
    '/login',
    '/static/logo.png',
    'https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap',
    'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'
];

// Install event - cache core assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                // addAll fails if ANY request fails; use individual adds for external URLs
                return Promise.allSettled(
                    STATIC_ASSETS.map(url => cache.add(url).catch(e => console.warn('[SW] Failed to cache:', url, e)))
                );
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - cleanup old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - cache first for static, network first for API
// Fetch event - Network-first for everything during development
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Skip non-GET and extension requests
    if (event.request.method !== 'GET' || url.protocol === 'chrome-extension:') return;

    // Network-First Strategy for ALL routes so updates show up immediately
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // If it's a valid response, save an updated copy to cache
                if (response && response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            })
            .catch(() => {
                // Fallback to cache if network is completely down
                return caches.match(event.request).then(cached => {
                    if (cached) return cached;
                    if (url.pathname.startsWith('/api/')) {
                        return new Response(JSON.stringify({ error: 'Offline' }), {
                            headers: { 'Content-Type': 'application/json' }
                        });
                    }
                    return caches.match('/login');
                });
            })
    );
});
