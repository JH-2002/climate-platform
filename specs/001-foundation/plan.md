# Plan 001 — Foundation

## Arquitetura envolvida
Ver `ARCHITECTURE.md` §1, §7, §8. Esta fase cria apenas `core`, infraestrutura e o shell do frontend.

## Componentes novos

### Repositório
```
climate-platform/
├── backend/
│   ├── app/
│   │   ├── main.py               # create_app()
│   │   ├── api/v1/health.py
│   │   ├── core/
│   │   │   ├── config.py         # Settings (pydantic-settings)
│   │   │   ├── logging.py        # structlog JSON
│   │   │   ├── middleware.py     # correlation id
│   │   │   ├── errors.py         # Problem Details
│   │   │   └── db.py             # engine/session async
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   └── tasks/system.py   # system.ping
│   │   └── tests/
│   ├── migrations/               # Alembic (0001_enable_postgis)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/(shell)/layout.tsx, page.tsx, status/page.tsx
│   ├── features/navigation/registry.ts
│   ├── features/system/useReadiness.ts
│   ├── components/ui/StatusBadge.tsx
│   ├── lib/api-client.ts
│   └── Dockerfile
├── scripts/smoke_sources.py
├── .github/workflows/ci.yml
├── docker-compose.yml
├── .env.example
└── .gitignore
```

Pastas de domínio (`risk/`, `simulation/` etc.) **não** são criadas agora (Constituição §8 e item 24 do documento mestre).

### Bibliotecas e justificativa
| Lib | Motivo |
|---|---|
| pydantic-settings | validação de configuração na inicialização (FR-012) |
| structlog | logs JSON com contexto (FR-006) |
| asyncpg + SQLAlchemy 2 async | acesso ao banco não bloqueante |
| redis-py | readiness e cache |
| celery[redis] | workers e beat |
| httpx | cliente HTTP (smoke test, adapters futuros) |
| import-linter | garantir fronteiras de módulos (ADR-001) |
| @tanstack/react-query | dados remotos com retry/estados |

## Alterações no banco
Migration `0001_enable_postgis`: `CREATE EXTENSION IF NOT EXISTS postgis;`. Nenhuma tabela de domínio.

## Contratos de API
```
GET /api/v1/health        → 200 {"status":"ok","version":"0.1.0"}
GET /api/v1/health/ready  → 200|503
{
  "status": "ok" | "degraded",
  "checked_at": "2026-11-19T15:00:00Z",
  "components": {
    "db":      {"status":"ok","latency_ms":3.1},
    "postgis": {"status":"ok","version":"3.4"},
    "redis":   {"status":"ok","latency_ms":0.8},
    "worker":  {"status":"unavailable","detail":"no reply in 2s"}
  }
}
```

## Fluxo de dados
Navegador → Next.js (`/status`) → `GET /api/v1/health/ready` → checagens em paralelo com timeout de 2 s cada → resposta agregada.

## Estratégia de testes
- Unit: settings faltando (AC-007), formatação de Problem Details, middleware de correlation ID.
- Integration (compose `test`): readiness com todos ok (AC-002) e com Redis indisponível via dependência sobrescrita (AC-003).
- Frontend: Vitest + Testing Library para `StatusBadge` e página `/status` nos estados loading/success/degraded/error (AC-005), com MSW simulando a API.
- Acessibilidade: axe na página `/status` (NFR-005).
- CI: AC-006.

## Segurança
`.env` ignorado; gitleaks no CI; CORS restrito a `FRONTEND_ORIGIN`; containers sem root quando a imagem permitir.

## Impacto em outros módulos
Nenhum (primeira fase). Define convenções que todas as próximas specs reutilizam.

## Ordem de execução
T001 → T002 → T003 → (T004, T005, T007 em paralelo) → T006 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015.

## Rollback
Fase sem dados de produção; rollback = reverter commits.
