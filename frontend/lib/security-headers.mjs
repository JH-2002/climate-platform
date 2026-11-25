// Cabeçalhos de segurança do frontend (spec 011, FR-170). Função pura, testada no Vitest.
// O provedor de mapas configurado entra na CSP para o mapa continuar funcionando (BR-171).

/** Origem ("https://host") de uma URL, ou null se não for http(s). */
export function originOf(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url.replace(/\{[a-z]\}/g, "0"));
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.origin : null;
  } catch {
    return null;
  }
}

/**
 * @param {{ dev: boolean, mapUrls: (string | undefined)[] }} options
 * @returns {{ key: string, value: string }[]}
 */
export function securityHeaders({ dev, mapUrls }) {
  const maps = [...new Set(mapUrls.map(originOf).filter(Boolean))];
  const external = maps.join(" ");
  const csp = [
    "default-src 'self'",
    // O Next injeta scripts inline; 'unsafe-eval' só em desenvolvimento (recarga do código).
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${external}`.trim(),
    `font-src 'self' data: ${external}`.trim(),
    `connect-src 'self' ${external}${dev ? " ws: wss:" : ""}`.trim(),
    "worker-src 'self' blob:",
    "child-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
  return [
    { key: "Content-Security-Policy", value: csp },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Frame-Options", value: "DENY" },
    {
      key: "Permissions-Policy",
      value: "geolocation=(self), camera=(), microphone=(), payment=(), usb=(), interest-cohort=()",
    },
  ];
}
