# Spec 001 — Foundation

> Status: **Concluída** (2026-11-19) · Fase: 1 · Depende de: Constituição v1.0.0

## Contexto
Nenhum código existe. Todas as fases seguintes precisam de um ambiente reproduzível com banco geoespacial, fila, API, workers, frontend, logs, testes e CI. Sem essa base, cada funcionalidade reinventaria configuração e o projeto perderia consistência.

## Objetivo
Entregar um esqueleto executável com um comando (`docker compose up`), em que todos os serviços sobem saudáveis, a API reporta seu estado real, o frontend exibe esse estado, e os testes e verificações de qualidade rodam localmente e no CI.

## Escopo
**Incluído:** repositório Git; Docker Compose (db PostGIS, redis, backend, worker, beat, frontend); configuração por ambiente; app FastAPI com healthchecks; logging estruturado com correlation ID; erros padronizados; Alembic com extensão PostGIS; Celery com tarefa de verificação; frontend Next.js com shell de navegação e página de status; ferramentas de qualidade; testes iniciais; CI; smoke test das fontes externas.

**Fora do escopo:** qualquer tabela de domínio (entram na spec 002); autenticação; mapas; gráficos; dados meteorológicos; deploy em nuvem.

## User stories
- **US-001** Como desenvolvedor, quero subir todo o ambiente com um comando para começar a trabalhar sem configuração manual.
- **US-002** Como operador, quero ver se API, banco, Redis e workers estão saudáveis para confiar no sistema.
- **US-003** Como desenvolvedor, quero que lint, tipos e testes rodem automaticamente para evitar regressões.
- **US-004** Como responsável pelo projeto, quero saber quais fontes externas realmente respondem a partir da minha máquina antes de escrever adapters.

## Requisitos funcionais
- **FR-001** `docker compose up` sobe `db`, `redis`, `backend`, `worker`, `beat` e `frontend`, cada um com healthcheck.
- **FR-002** `GET /api/v1/health` retorna `200 {"status":"ok"}` se o processo da API está vivo (sem consultar dependências).
- **FR-003** `GET /api/v1/health/ready` verifica banco (incluindo `postgis_version()`), Redis e ao menos um worker Celery respondendo; retorna `200` se todos OK, `503` caso contrário, com o estado de cada componente e latência medida.
- **FR-004** Toda requisição recebe/propaga `X-Correlation-ID`; o valor aparece em todos os logs daquela requisição e no corpo de erro.
- **FR-005** Erros da API seguem RFC 9457 (Problem Details) com `correlation_id`.
- **FR-006** Logs em JSON com `timestamp` (UTC ISO-8601), `level`, `event`, `correlation_id`, `service`.
- **FR-007** Alembic aplica migrations no boot do serviço `backend` (comando explícito, não implícito no import) e a primeira migration habilita `postgis`.
- **FR-008** Celery possui a tarefa `system.ping` usada pelo readiness check.
- **FR-009** O frontend exibe uma página `/status` que consome `/api/v1/health/ready` e mostra cada componente com estado textual + ícone, latência e horário da verificação.
- **FR-010** O shell do frontend mostra apenas itens de navegação de módulos implementados (lista em `features/navigation/registry.ts`); módulos futuros não aparecem como links vazios.
- **FR-011** `scripts/smoke_sources.py` testa as fontes da Fase 2 e grava o resultado em `docs/data-sources/smoke-results.md` (HTTP status, latência, amostra de campos, data/hora).
- **FR-012** Variáveis de ambiente documentadas em `.env.example`; a aplicação falha na inicialização com mensagem clara se uma variável obrigatória faltar.

## Requisitos não funcionais
- **NFR-001** Ambiente sobe em < 3 min numa máquina com imagens já baixadas.
- **NFR-002** `/health` responde em < 50 ms (p95, local).
- **NFR-003** Nenhum secret versionado; `.env` no `.gitignore`; verificação por `gitleaks` ou equivalente no CI.
- **NFR-004** Funciona em Windows (Docker Desktop + WSL2) e Linux.
- **NFR-005** Página `/status` passa em axe sem violações sérias/críticas.

## Regras de negócio
- **BR-001** O readiness nunca reporta `ok` para um componente que não foi efetivamente consultado nesta requisição (sem cache de status > 5 s).
- **BR-002** Fixtures/seeds de teste só carregam se `APP_ENV in {"test","development"}`.

## Critérios de aceite
- **AC-001** *Given* um clone limpo e `.env` copiado de `.env.example`, *When* executo `docker compose up -d`, *Then* `docker compose ps` mostra os 6 serviços `healthy` em até 3 min.
- **AC-002** *Given* o ambiente rodando, *When* chamo `/api/v1/health/ready`, *Then* recebo `200` com `db`, `postgis`, `redis` e `worker` como `ok` e latências numéricas.
- **AC-003** *Given* o serviço `redis` parado, *When* chamo `/api/v1/health/ready`, *Then* recebo `503` com `redis: "unavailable"` e os demais componentes com seu estado real.
- **AC-004** *Given* uma requisição com `X-Correlation-ID: abc`, *When* ela gera um erro 404, *Then* a resposta é Problem Details com `correlation_id: "abc"` e o log JSON da requisição contém `"correlation_id":"abc"`.
- **AC-005** *Given* o frontend aberto em `/status`, *When* a API está indisponível, *Then* a página mostra estado de erro com mensagem compreensível e botão "Tentar novamente" que refaz a consulta.
- **AC-006** *Given* um PR, *When* o CI roda, *Then* ruff, mypy, import-linter, ESLint, `tsc --noEmit`, pytest e Vitest executam e o PR falha se qualquer um falhar.
- **AC-007** *Given* `DATABASE_URL` ausente, *When* o backend inicia, *Then* ele termina com código ≠ 0 e log `missing_required_setting` citando a variável.
- **AC-008** *Given* acesso à internet na máquina do desenvolvedor, *When* executo `python scripts/smoke_sources.py`, *Then* `smoke-results.md` é gerado com uma linha por endpoint testado, incluindo falhas.

## Estados (página /status)
`loading` (skeleton) · `success` · `degraded` (algum componente falhou) · `error` (API inacessível) · `offline` (navegador sem rede).

## Dependências
Docker Desktop; imagens `postgis/postgis`, `redis`, `python:3.12-slim`, `node:22`; GitHub (CI).

## Riscos e limitações
- **R-001** Docker Desktop no Windows com volume em `F:` pode ter I/O lento → usar volumes nomeados para o banco e `node_modules`.
- **R-002** Sem rede no ambiente de execução da IA, o smoke test precisa ser executado pelo responsável na própria máquina.
- **R-003** Versões de imagem flutuantes quebram reprodutibilidade → fixar tags exatas.
