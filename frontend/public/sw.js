/*
 * Service worker da plataforma (spec 013, FR-203). Serve a plataforma e a vitrine pública:
 * o prefixo do site chega na URL de registro (sw.js?base=/climate-platform).
 *
 * - Arquivos estáticos do Next (_next/static, ícones, worker do mapa): cache primeiro.
 * - Telas (navegação): rede primeiro; sem rede, a última versão guardada.
 * - Leituras da API e dados da vitrine: rede primeiro com até 8 s; sem rede, a última resposta
 *   guardada. Escritas (POST) nunca passam pelo cache.
 */
const VERSION = "v1";
const BASE = new URL(self.location.href).searchParams.get("base") || "";
const STATIC_CACHE = `clima-static-${VERSION}`;
const PAGES_CACHE = `clima-paginas-${VERSION}`;
const DATA_CACHE = `clima-dados-${VERSION}`;
const DATA_LIMIT = 300;
const NETWORK_TIMEOUT_MS = 8000;

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  const keep = new Set([STATIC_CACHE, PAGES_CACHE, DATA_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("clima-") && !keep.has(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isStatic(path) {
  return (
    path.startsWith(`${BASE}/_next/static/`) ||
    path.startsWith(`${BASE}/icons/`) ||
    path.startsWith(`${BASE}/vendor/`)
  );
}

function isData(path) {
  return path.startsWith(`${BASE}/api/v1/`) || path.startsWith(`${BASE}/demo-data/`) || path.startsWith("/api/v1/");
}

async function trim(cacheName, limit) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - limit)).map((k) => cache.delete(k)));
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) (await caches.open(STATIC_CACHE)).put(request, response.clone());
  return response;
}

async function networkFirst(request, cacheName, timeoutMs) {
  const cache = await caches.open(cacheName);
  try {
    const response = await Promise.race([
      fetch(request),
      new Promise((_, reject) => setTimeout(() => reject(new Error("tempo esgotado")), timeoutMs)),
    ]);
    if (response.ok) {
      await cache.delete(request);
      await cache.put(request, response.clone());
      if (cacheName === DATA_CACHE) trim(DATA_CACHE, DATA_LIMIT);
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isStatic(url.pathname)) {
    event.respondWith(cacheFirst(request));
  } else if (isData(url.pathname)) {
    event.respondWith(networkFirst(request, DATA_CACHE, NETWORK_TIMEOUT_MS));
  } else if (request.mode === "navigate" || request.headers.get("RSC") === "1") {
    // Telas: a navegação completa e os pedidos de tela do próprio Next (RSC) entre páginas.
    event.respondWith(networkFirst(request, PAGES_CACHE, NETWORK_TIMEOUT_MS));
  }
});
