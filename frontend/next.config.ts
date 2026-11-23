import type { NextConfig } from "next";

/**
 * Proxy same-origin opcional (`/api/*` → FastAPI).
 *
 * Útil no deploy (Vercel, #83): com o PWA e a API sob o mesmo domínio, o cookie
 * HttpOnly `vezo_session` (SameSite=Lax) é enviado sem depender de CORS/terceiros.
 * Ative definindo `API_PROXY_TARGET` (ex.: http://localhost:8000) e
 * `NEXT_PUBLIC_API_URL=/api`. Sem `API_PROXY_TARGET`, nenhum rewrite é criado.
 */
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async redirects() {
    // A rota do Dashboard é "/"; "/rotina" é mantida como alias citado na #47.
    return [{ source: "/rotina", destination: "/", permanent: false }];
  },
  async rewrites() {
    if (!apiProxyTarget) return [];
    return [{ source: "/api/:path*", destination: `${apiProxyTarget}/:path*` }];
  },
};

export default nextConfig;
