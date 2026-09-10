// წმიდა წერილი - Service Worker
// ყოველ ცვლილებაზე გავზარდოთ CACHE_VERSION (მაგ: bible-v11, bible-v12...)
// ეს უზრუნველყოფს რომ მომხმარებლებმა მიიღონ ახალი ვერსია
const CACHE_VERSION = "bible-v71";
// APP_SHELL-ში არ ვუთითებთ ?v=N-ს - runtime fetch handler აკეშავს
// იმ ვერსიას რომელსაც index.html რეალურად ითხოვს
const APP_SHELL = [
  "/",
  "/static/index.html",
  "/static/style.min.css",
  "/static/highlights.min.js",
  "/static/lexicon.min.js",
  "/static/export-import.min.js",
  "/static/audio.min.js",
  "/static/commentary.min.js",
  "/static/app.min.js",
  "/static/tags.min.js",
  "/static/study-pad.min.js",
  "/static/topical.min.js",
  "/static/word-study.min.js",
  "/static/manifest.json",
  "/static/icon.svg",
  "/static/favicon.png",
  "/static/fonts/noto-serif-georgian.woff2",
  "/static/fonts/noto-sans-georgian.woff2",
  "/favicon.ico",
];

// Install - app shell-ის კეშირება
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.addAll(APP_SHELL).catch((err) => {
        console.warn("[SW] App shell ნაწილი ვერ დაკეშირდა:", err);
      })
    )
  );
  self.skipWaiting();
});

// Activate - ძველი კეშების გასუფთავება + გვერდის განახლება
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim()).then(() =>
      // client.navigate() ვერ მუშაობს URL-ებზე # fragment-ით,
      // ამიტომ ვაგზავნით message-ს რომ გვერდმა თავი განაახლოს.
      self.clients.matchAll().then((clients) =>
        clients.forEach((client) =>
          client.postMessage({ type: "SW_UPDATED" })
        )
      )
    )
  );
});

// Fetch - სტრატეგია მიხედვით URL-ის
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // მხოლოდ http/https რექვესთები ვამუშავებთ - chrome-extension:// და
  // სხვა სქემები ვერ დაკეშირდება და იწვევს TypeError-ს.
  if (url.protocol !== "http:" && url.protocol !== "https:") return;

  // გარე დომენების მოთხოვნები (cloudflareinsights, analytics, CDN)
  // საერთოდ არ ვაკეშირებთ და არ ჩავერებით - ბრაუზერმა პირდაპირ გაატაროს.
  if (url.origin !== self.location.origin) return;

  // დამხმარე ფუნქცია: უსაფრთხოდ ვაკეთებთ cache.put-ს (მხოლოდ ok პასუხები)
  const safePut = (cache, request, response) => {
    // აუდიო/ვიდეო ფაილები არ დავაკეშიროთ (დიდი ფაილებია, 206 partial response)
    const url = new URL(request.url);
    if (url.pathname.startsWith("/static/audio/")) return;
    // მხოლოდ სრული 200 OK პასუხები (206 partial არ მუშაობს cache.put-თან)
    if (response.ok && response.status === 200 && response.type === "basic") {
      cache.put(request, response.clone());
    }
  };

  // ნავიგაცია (HTML) - network first, cache fallback
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => safePut(c, req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match("/")).catch(() => caches.match("/")))
    );
    return;
  }

  // API - network first, cache fallback
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => safePut(c, req, copy));
          return res;
        })
        .catch(() => caches.match(req).catch(() => new Response("{}", {status: 503, headers: {"Content-Type": "application/json"}})))
    );
    return;
  }

  // Static assets (JS/CSS/HTML/JSON/SVG) - network first, cache fallback
  // ეს უზრუნველყოფს რომ ყოველთვის ახალი ვერსია მივიღოთ, offline-ში კი კეშიდან
  // აუდიო ფაილები გამოვრიცხოთ - დიდი ფაილებია და 206 partial response იწვევს შეცდომას
  if (url.pathname.startsWith("/static/audio/")) {
    e.respondWith(fetch(req).catch(() => caches.match(req).catch(() => new Response("", {status: 503}))));
    return;
  }
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => safePut(c, req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).catch(() => new Response("", {status: 503})))
  );
});

// მესიჯი გვერდისგან - დაელოდე SKIP_WAITING-ს რომ აქტიური გავხდეთ
self.addEventListener("message", (e) => {
  if (e.data && e.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
