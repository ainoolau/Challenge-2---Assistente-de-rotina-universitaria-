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

/**
 * Origens adicionais permitidas em desenvolvimento (`next dev -H 0.0.0.0`),
 * separadas por vírgula (ex.: `ALLOWED_DEV_ORIGINS=192.168.10.253`).
 * Permite testar o PWA no celular na mesma rede Wi-Fi sem bloquear `/_next/*`.
 */
const allowedDevOrigins = (process.env.ALLOWED_DEV_ORIGINS ?? "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
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
