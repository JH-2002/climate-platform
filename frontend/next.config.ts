import type { NextConfig } from "next";
import { mapSourceUrls } from "./lib/map-sources.mjs";
import { securityHeaders } from "./lib/security-headers.mjs";

// O navegador fala só com a origem do frontend; o Next encaminha /api/* para o backend.
// Assim não há chamadas entre origens (CORS) e o endereço interno do backend não vaza.
const apiInternalUrl = (process.env.API_INTERNAL_URL ?? "http://backend:8000").replace(/\/+$/, "");

// Vitrine pública (spec 012): site estático no GitHub Pages, sem servidor, sem /api nem cabeçalhos
// (o Pages não aplica cabeçalhos próprios). As respostas da API vêm de demo-data/ (lib/demo.ts).
const demo = process.env.NEXT_PUBLIC_DEMO === "1";
const demoConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "export",
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
  trailingSlash: true,
  images: { unoptimized: true },
};

const serverConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Build de produção autocontido (spec 011): a imagem leva só o necessário para `node server.js`.
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders({
          dev: process.env.NODE_ENV !== "production",
          mapUrls: mapSourceUrls({
            style: process.env.NEXT_PUBLIC_MAP_STYLE_URL,
            terrain: process.env.NEXT_PUBLIC_TERRAIN_TILES_URL,
          }),
        }),
      },
    ];
  },
};

export default demo ? demoConfig : serverConfig;
