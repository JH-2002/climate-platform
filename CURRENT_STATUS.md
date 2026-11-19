# CURRENT STATUS

> Atualizado em: 2026-11-19

## Fase atual
**Fase 1 — Foundation: implementada e validada no CI; faltam as verificações locais.**

## Repositório
- GitHub: https://github.com/JH-2002/climate-platform (público), branch `main`.
- Cópia local: `F:\dev\climate-platform`, com `origin` apontando para o GitHub.

## Validado no CI (GitHub Actions, commit `f211a28`)
- Backend: ruff, mypy estrito, import-linter, `alembic upgrade head` com PostGIS, 35 testes (unitários e integração com PostgreSQL/PostGIS, Redis e worker Celery reais — AC-002, AC-003, AC-004, AC-007), pip-audit.
- Frontend: ESLint, `tsc --noEmit`, testes Vitest com axe (AC-005, NFR-005), `npm audit` das dependências de produção.
- Varredura de segredos (gitleaks).

## Pendente (máquina local)
1. `docker compose up -d --build` com os 6 serviços `healthy` (AC-001).
2. Abrir http://localhost:3000/status no navegador.
3. `python scripts/smoke_sources.py` (AC-008) e atualizar `docs/data-sources/SOURCES.md`.
4. Gerar e versionar `frontend/package-lock.json` (README › Executar). O CI também publica os locks como artefatos em cada execução.

## Bloqueios externos
- Token do INMET: e-mail enviado em 2026-11-19, aguardando resposta.

## Pendências técnicas registradas
- Migrar Vitest 2 → versão principal atual (alertas de segurança restritos à ferramenta de teste).
- Avaliar Next 16, Python 3.15 e Node 26 (o Dependabot ignora versões principais até a decisão).

## Próxima tarefa
Concluir as verificações locais → plan/tasks da spec 002 (Data Ingestion).
