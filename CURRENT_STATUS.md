# CURRENT STATUS

> Atualizado em: 2026-11-19

## Fase atual
**Fase 1 — Foundation: implementada, validação local pendente.**
Fase 0 aprovada pelo responsável em 2026-11-19.

## Concluído
- Fase 0: constituição, arquitetura, ADRs 001–006, validação documental das fontes, specs.
- Fase 1 (código): Docker Compose com 6 serviços e healthchecks; backend FastAPI (config validada, logs JSON com correlation ID e redação de segredos, Problem Details, `/health`, `/health/ready`); Alembic com PostGIS; Celery worker + beat com heartbeat; frontend Next.js com navegação dirigida por registro e página `/status`; testes; CI; pre-commit; script de smoke test das fontes.
- Repositório Git inicializado com commit inicial.

## Validado
- 30 testes unitários (lógica de readiness, Problem Details, correlation ID, redação de segredos, heartbeat, script de fontes) — passando.
- `docker compose config` válido; YAML/TOML válidos.
- Módulos TypeScript puros (cliente de API, registro de navegação, estado de UI, formatação) com type-check e verificação comportamental.

## Não validado ainda (motivo: sem Docker e sem acesso a pacotes no ambiente da IA)
- Subida dos containers (AC-001), readiness real (AC-002/003), logs e erros via HTTP (AC-004), página `/status` no navegador (AC-005), CI (AC-006), testes que dependem de FastAPI/pydantic-settings/Vitest.
- Smoke test real das fontes (AC-008).
→ Roteiro em README › "Validação da Fase 1".

## Bloqueios e ações do responsável
1. **Instalar Docker Desktop** (não encontrado no Windows; WSL já está instalado).
2. **Enviar o e-mail de pedido de token ao INMET** (cadastro.act@inmet.gov.br) — bloqueia observações reais na Fase 2.
3. Rodar `python scripts/smoke_sources.py` e o roteiro de validação.
4. (Opcional) Criar repositório no GitHub e fazer push para ativar o CI.

## Próxima tarefa
Validação local da Fase 1 → depois, plan/tasks da spec 002 (Data Ingestion).

## Problemas conhecidos
- `ruff format --check` e Prettier podem apontar ajustes de formatação na primeira execução (código escrito sem os formatadores disponíveis). Rodar `ruff format .` e `npm run format` uma vez e commitar.
- Versões das dependências fixadas com base no conhecimento disponível; se alguma versão não for encontrada no `pip`/`npm`, atualizar para a mais próxima e registrar.
