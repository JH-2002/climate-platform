# Plan 011 — Hardening

## Decisões
- **Caddy na frente** ([ADR-016](../../docs/architecture/adr/ADR-016-production-stack.md)): HTTPS automático (Let's Encrypt), HSTS, compressão e um `Caddyfile` curto. O Next continua sendo a única origem que o navegador vê (proxy `/api` já existente), então não há CORS entre origens.
- **Limite de requisições na API, no Redis já existente.** Middleware ASGI puro (`app/core/rate_limit.py`): chave `rl:{grupo}:{hash do IP}:{minuto}`, `INCR` + `EXPIRE` num pipeline. A regra (grupo da rota, limite) é uma função pura testada sem Redis.
- **Cabeçalhos no Next via `headers()` do `next.config.ts`**, montados por uma função pura (`lib/security-headers.mjs`) testada no Vitest. Sem middleware de nonce (ver riscos da spec).
- **Imagens de produção separadas das de desenvolvimento.** `frontend/Dockerfile.prod` (multi-stage, `output: "standalone"`, usuário `nextjs`); `backend/Dockerfile` ganha um alvo `prod` sem as dependências de desenvolvimento.
- **Backup com a própria imagem do Postgres** num laço `sleep` até as 03h (sem cron, sem imagem extra).
- **E2E com Playwright instalado só no job do CI** (`npx playwright@<versão> install --with-deps chromium`), contra `next build && next start`, com a API simulada por `page.route`. Os testes ficam em `frontend/e2e/`, fora do `tsc` e do Vitest da aplicação.

## Backend
| Arquivo | Conteúdo |
|---|---|
| `core/rate_limit.py` | Regras (puras), extração do IP com proxies confiáveis, middleware |
| `core/security.py` | Middleware de cabeçalhos e de tamanho do corpo |
| `core/config.py` | `trusted_proxies`, limites, validação de produção |
| `main.py` | Ordem dos middlewares |
| `Dockerfile` | Alvo `prod` |

## Frontend
| Arquivo | Conteúdo |
|---|---|
| `lib/security-headers.mjs` | CSP e demais cabeçalhos, por ambiente |
| `next.config.ts` | `headers()` e `output: "standalone"` |
| `Dockerfile.prod` | Build de produção |
| `e2e/*.spec.ts`, `e2e/fixtures/*.json`, `playwright.config.ts` | Testes ponta a ponta |

## Operação
- `docker-compose.prod.yml`, `deploy/Caddyfile`, `.env.prod.example`, `deploy/backup.sh`, `scripts/restore.sh`, `scripts/perf_check.py`, `docs/operations/RUNBOOK.md`.

## Testes
- Unitários: regras de limite, IP com proxy confiável, cabeçalhos, validação de produção, CSP.
- Integração: 429 com Redis real (AC-171), falha aberta (AC-172), 413 (AC-174).
- E2E: FR-179 no job novo do CI.
- Manual: pilha de produção no Docker local (sem domínio, Caddy com certificado interno), backup e restauração (AC-176), metas de desempenho (FR-180).

## Ordem
1. Parte A (aplicação) → 2. Parte C (E2E no CI) → 3. Parte B (produção e operação, validação no Docker local).
