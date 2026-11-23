# Vezo — PWA (`frontend/`)

Interface oficial do Vezo: **Next.js 16 (App Router) + React 19 + TypeScript strict + Tailwind CSS v4 + shadcn/ui (Radix) + lucide-react**.
Diretrizes visuais e de UX: [`docs/DESIGN.md`](../docs/DESIGN.md). Contratos da API: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) §5.

## Rodando localmente

Requisitos: **Node.js >= 20.9** e a API FastAPI rodando na porta 8000.

```bash
# 1. API (na raiz do repositório)
uvicorn src.api.main:app --reload            # http://localhost:8000 (CORS já libera :3000)

# 2. PWA
cd frontend
cp .env.example .env.local                   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install                                  # também roda `next typegen`
npm run dev                                  # http://localhost:3000
```

| Comando | O que faz (mesmo que o CI `Frontend / *`) |
| :--- | :--- |
| `npm run lint` | ESLint (`eslint-config-next`) |
| `npm run typecheck` | `next typegen && tsc --noEmit` |
| `npm run build` | Build de produção (Turbopack) |

> Nunca versione `node_modules/`, `.next/`, `.env.local` nem `next-env.d.ts` (já estão no `.gitignore`).

## Estrutura

```
src/
├── app/                      # Rotas (App Router)
│   ├── page.tsx              # "/"  Dashboard de Rotina (+ Chat ao lado no desktop) — #48
│   ├── chat/page.tsx         # "/chat" Assistente — #49
│   ├── onboarding/page.tsx   # "/onboarding" Sessão, consentimento e preferências — #45
│   ├── manifest.ts           # /manifest.webmanifest (PWA instalável)
│   ├── icon.tsx, apple-icon.tsx  # ícones PNG gerados em build (sem binários no Git)
│   ├── loading.tsx, error.tsx, not-found.tsx
│   └── globals.css           # Tailwind v4 + mapeamento dos tokens (@theme inline)
├── styles/tokens.css         # FONTE ÚNICA das cores/tipografia (#46)
├── components/
│   ├── ui/                   # shadcn/ui (ajustados: alvos >= 44px, variantes warning/success/proposal)
│   ├── layout/               # AppShell: header desktop + barra inferior mobile
│   ├── states/               # PageSkeleton, ScheduleSkeleton, EmptyState, ErrorState, ConnectionBanner
│   ├── providers/            # SessionProvider (useSession)
│   └── features/             # routine/, chat/, onboarding/
├── hooks/                    # useApiHealth, useOnlineStatus
├── lib/api.ts                # Cliente HTTP tipado
└── types/api.ts              # Espelho de src/api/schemas.py + src/core/schemas.py
```

## Como usar nas próximas tasks (#45, #48, #49)

**Chamar a API** — sempre pelo cliente tipado; nunca use `fetch` direto:

```tsx
import { api, isApiError } from "@/lib/api";

try {
  const agenda = await api.schedule.list({ horizon_start, horizon_end });
} catch (error) {
  if (isApiError(error) && error.kind === "conflict") {
    // 409: sono protegido / item fixo / proposta defasada → error.message já vem em português
  }
}
```

- `credentials: "include"` já está embutido: o cookie HttpOnly `vezo_session` vai em toda chamada. **Não** guarde o `session_token` em `localStorage`.
- Erros viram `ApiError` com `kind`: `unauthorized` (401), `not_found`, `conflict` (409), `validation` (422, com `fieldErrors` por campo), `unavailable` (503), `network`, `unknown`.
- `api.schedule.confirmProposal()` só deve ser chamado após clique explícito em **"Confirmar e aplicar"**.

**Sessão** — `const { state, refresh, createSession } = useSession();` com `state.status` = `loading | authenticated | anonymous | error`.

**Estados prontos** — `<ScheduleSkeleton />`, `<PageSkeleton />`, `<EmptyState icon=… title=… action=… />`, `<ErrorState error={apiError} onRetry={…} />`. O `<ConnectionBanner />` global já trata offline e API fora do ar.

**Cores** — use somente classes de token: `bg-primary`, `text-muted-foreground`, `bg-warning-subtle`, `border-slot-study-proposed`, `bg-slot-class-bg`… ou as classes prontas `.vezo-slot-*` de `tokens.css`. Nada de hexadecimal em componentes. Para mudar a paleta, altere apenas `src/styles/tokens.css`.

**Layout** — `lg:` (>= 1024px) é o breakpoint do desktop em duas colunas; abaixo disso vale a barra inferior. Botões, abas e inputs já têm altura mínima de 44px.

## Proxy same-origin (deploy #83)

Para servir a API sob o mesmo domínio do PWA (cookie first-party):

```bash
NEXT_PUBLIC_API_URL=/api
API_PROXY_TARGET=https://sua-api.exemplo.com
```

`next.config.ts` cria o rewrite `/api/:path*` → `API_PROXY_TARGET` apenas quando a variável existe.

## Testando no celular (mesma rede Wi-Fi)

Para validar o layout mobile e o fluxo real da API direto no celular conectado ao mesmo Wi-Fi do computador:

1. Descubra o IP local do PC (Windows: `ipconfig` → Endereço IPv4; Linux/macOS: `hostname -I`).
2. Configure `frontend/.env.local` com o proxy same-origin e o IP liberado no dev server:

```bash
NEXT_PUBLIC_API_URL=/api
API_PROXY_TARGET=http://127.0.0.1:8000
ALLOWED_DEV_ORIGINS=192.168.0.100   # troque pelo IPv4 do seu PC
```

3. Suba a API na raiz (`uvicorn src.api.main:app --host 127.0.0.1 --port 8000`) e o frontend na rede local:

```bash
cd frontend
npm run dev:lan                     # ou: npm run build && npm run start:lan
```

4. Acesse `http://<IP-DO-PC>:3000` no navegador do celular. O proxy `/api/*` mantém o cookie `HttpOnly` funcionando sem CORS nem necessidade de expor a porta `8000`. *(Obs.: o botão nativo de instalar PWA no celular exige HTTPS — em HTTP local você valida layout, toque, sessão e API; a instalação nativa é validada em `localhost` no desktop ou após o deploy HTTPS.)*
