import type { NextConfig } from "next";

// O navegador fala só com a origem do frontend; o Next encaminha /api/* para o backend.
// Assim não há chamadas entre origens (CORS) e o endereço interno do backend não vaza.
const apiInternalUrl = (process.env.API_INTERNAL_URL ?? "http://backend:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }];
  },
};

export default nextConfig;
