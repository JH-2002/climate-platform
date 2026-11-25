# Tasks 001 — Foundation

Legenda: `[ ]` pendente · `[i]` implementada, validação completa pendente (exige Docker/dependências na máquina local) · `[x]` concluída e validada.

> Validação (2026-11-19): CI do GitHub Actions verde no commit `f211a28` — ruff, mypy estrito, import-linter, migração Alembic com PostGIS real, 35 testes de backend (unitários + integração com PostgreSQL/PostGIS, Redis e worker Celery reais), testes do script de fontes, ESLint, `tsc`, testes Vitest com axe e auditorias de dependências. Validação local concluída em 2026-11-19: 6 serviços `healthy` (AC-001), página `/status` verificada no navegador (AC-005) e smoke test das fontes (AC-008, ver `docs/data-sources/smoke-results.md`). A validação local revelou e corrigiu: healthcheck do banco via TCP, chamada da API pela mesma origem e ping do worker sem espera.

| ID | Tarefa | Arquivos | Depende de | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|---|
| T001 | Repositório Git, `.gitignore`, `.editorconfig`, `.gitattributes` | raiz | — | repositório com commit inicial; `.env` ignorado | — | [x] |
| T002 | `docker-compose.yml` (db PostGIS, redis, backend, worker, beat, frontend) + `.env.example` | raiz | T001 | `docker compose config` válido ✔; 6 serviços `healthy` (AC-001) | manual | [x] |
| T003 | Esqueleto backend, `create_app()`, `Settings` validado | `backend/app/main.py`, `core/config.py`, `Dockerfile` | T002 | AC-007 | `test_config.py` | [x] |
| T004 | Logging JSON + correlation ID + redação de segredos | `core/logging.py`, `core/middleware.py`, `core/correlation.py`, `core/redaction.py` | T003 | FR-004/FR-006 | `test_redaction.py` ✔, `test_problem_and_correlation.py` ✔, `test_api_contract.py` | [x] |
| T005 | Banco async + Alembic + `0001_enable_postgis` | `core/resources.py`, `migrations/` | T003 | `alembic upgrade head` | integration | [x] |
| T006 | `/health` e `/health/ready` | `api/v1/health.py`, `core/health.py` | T004, T005, T008 | AC-002, AC-003 | `test_health_logic.py` ✔ (7), `test_readiness.py` | [x] |
| T007 | Problem Details (RFC 9457) | `core/problem.py`, `core/errors.py` | T004 | AC-004 | `test_problem_and_correlation.py` ✔, `test_api_contract.py` | [x] |
| T008 | Celery app, worker, beat, `system.ping`, `system.heartbeat`, healthchecks | `workers/` | T003 | worker responde ao ping; beat com heartbeat recente | `test_healthcheck.py` ✔ | [x] |
| T009 | Frontend: Next.js + TS strict + Tailwind + TanStack Query; shell com `registry.ts` | `frontend/` | T002 | FR-010 | `registry.test.ts` (lógica verificada ✔) | [x] |
| T010 | Página `/status` com estados loading/success/degraded/error/offline | `app/status/`, `components/system/`, `features/system/` | T006, T009 | AC-005; axe sem violações sérias | `ReadinessView.test.tsx`, `system.test.ts` | [x] |
| T011 | ruff, mypy, import-linter, ESLint, Prettier, pre-commit | configs | T003, T009 | comandos passam | — | [x] |
| T012 | Infra de testes (pytest + Vitest) | `backend/app/tests/`, `frontend/tests/` | T006, T010 | um comando roda tudo | todos | [x] |
| T013 | CI GitHub Actions (lint, tipos, testes, integração, gitleaks, audits) | `.github/workflows/ci.yml` | T011, T012 | AC-006 | CI | [x] |
| T014 | `scripts/smoke_sources.py` (stdlib) + execução na máquina do responsável | `scripts/` | — | AC-008; `SOURCES.md` atualizado com status real | `test_smoke_sources.py` ✔ (5) | [x] |
| T015 | README, `CURRENT_STATUS.md`, revisão de diff | docs | todas | DoD verificado | — | [x] |

✔ = executado e passando no ambiente da IA; [x] = validado no CI.

## Desvios do plano (registrados)
- **MSW não foi adicionado**: os testes de cliente usam `fetchImpl` injetável, o que dispensa a dependência.
- **`system.heartbeat` + healthcheck do beat**: o plano não definia como verificar o beat. O beat agenda um heartbeat a cada 30 s; o worker grava em Redis; o healthcheck do container exige heartbeat com menos de 120 s. O heartbeat **não** entra no `/health/ready` (escopo da FR-003 mantido).
- **Porta do banco no host = 5433**: há um PostgreSQL nativo instalado no Windows do responsável (5432).
- **`format:check` (Prettier) fora do CI** até o primeiro `npm run format` ser executado com as dependências instaladas.

## Traceability

| Requisito | Tarefas | Implementação | Teste | Aceite |
|---|---|---|---|---|
| FR-001 | T002, T008, T009 | `docker-compose.yml` | roteiro manual README | AC-001 |
| FR-002 | T006 | `api/v1/health.py::liveness` | `test_api_contract.py::test_liveness_returns_ok_and_version` | — |
| FR-003 | T006 | `core/health.py`, `core/resources.py`, `workers/control.py` | `test_health_logic.py`, `integration/test_readiness.py` | AC-002, AC-003 |
| FR-004 | T004 | `core/correlation.py`, `core/middleware.py` | `test_problem_and_correlation.py`, `test_api_contract.py` | AC-004 |
| FR-005 | T007 | `core/problem.py`, `core/errors.py`, `core/middleware.py` (500) | idem | AC-004 |
| FR-006 | T004 | `core/logging.py`, `core/redaction.py` | `test_redaction.py`, `test_api_contract.py` | AC-004 |
| FR-007 | T005 | `migrations/versions/0001_enable_postgis.py` | `integration/test_readiness.py` (postgis ok) | AC-002 |
| FR-008 | T008 | `workers/tasks/system.py` | `integration/test_readiness.py` (worker ok) | AC-002 |
| FR-009 | T010 | `app/status/page.tsx`, `components/system/ReadinessView.tsx` | `ReadinessView.test.tsx` | AC-005 |
| FR-010 | T009 | `features/navigation/registry.ts`, `components/layout/Sidebar.tsx` | `registry.test.ts` | — |
| FR-011 | T014 | `scripts/smoke_sources.py` | `scripts/tests/test_smoke_sources.py` | AC-008 |
| FR-012 | T003 | `core/config.py` | `test_config.py` | AC-007 |
| NFR-003 | T013 | `.gitignore`, gitleaks (CI e pre-commit), `core/redaction.py` | `test_redaction.py` | — |
| NFR-005 | T010 | `ReadinessView.tsx` | `ReadinessView.test.tsx` (axe) | — |
