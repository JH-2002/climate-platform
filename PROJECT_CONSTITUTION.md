# PROJECT CONSTITUTION — Climate Intelligence Platform

> Versão: 1.2.0 · Criada em: 2026-11-19 · Status: **Aprovada (2026-11-19)**
> Esta é a referência permanente do projeto. Qualquer alteração exige registro em `DECISIONS.md`, justificativa e análise de impacto.

---

## 1. Objetivo e escopo

Construir uma plataforma web de inteligência climática para **monitoramento meteorológico, análise de dados, visualização geoespacial, estimativa de condições favoráveis a alagamentos, simulação de cenários e relatórios**, com dados reais e rastreáveis.

**Região piloto:** Município de São Paulo, com expansão para a RMSP (ADR-002). A arquitetura não pode assumir uma única cidade — região é configuração, não código.

**Fora de escopo permanente (salvo nova decisão):**
- Emitir alertas públicos oficiais ou substituir órgãos de Defesa Civil.
- Afirmar previsão validada de desastres.
- Modelagem hidrológica/hidráulica física (ex.: HEC-RAS) na versão 1.

## 2. Arquitetura

- **Monólito modular** (backend FastAPI) + **workers Celery** separados + frontend Next.js (ADR-001).
- Sem microserviços, Kubernetes ou ML até haver necessidade documentada.
- Módulos com fronteiras explícitas; um módulo só acessa outro por sua interface pública (`service`), nunca por suas tabelas ou internals.
- Dependências permitidas: `api → services → repositories → models`; `integrations` e `ingestion` não conhecem `api`, `risk` ou frontend.

## 3. Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript (strict), Tailwind CSS, TanStack Query, Recharts, MapLibre GL (mapa 2D/3D, ADR-009); Three.js/R3F só no módulo de análise 3D (lazy) |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, GeoAlchemy2 |
| Banco | PostgreSQL 16 + PostGIS 3 |
| Processamento | Redis, Celery, Celery Beat |
| Infra | Docker, Docker Compose, healthchecks, logs estruturados (JSON) |
| Testes | pytest, pytest-asyncio, httpx; Vitest + Testing Library; Playwright (E2E); axe (acessibilidade) |
| Qualidade | ruff, mypy, ESLint, Prettier, TypeScript `strict` |

Versões exatas são fixadas na Fase 1 e registradas em `docs/architecture/`.

## 4. Padrões de código

- Type hints obrigatórios (Python) e `strict` (TS). Nada de `any` sem comentário justificando.
- Funções pequenas, nomes descritivos, uma responsabilidade.
- Lógica de negócio **nunca** em componentes visuais nem em rotas da API; fica em `services/` (backend) e `features/` ou `lib/` (frontend).
- Sem dependências circulares; sem abstrações para integrações que ainda não existem.
- Erros tratados explicitamente; nada de `except: pass`.

## 5. Segurança

- Secrets apenas em variáveis de ambiente; `.env` nunca versionado; `.env.example` sem valores reais.
- Senhas com Argon2id. Tokens com expiração.
- CORS restrito por ambiente. Validação de entrada com Pydantic em toda borda.
- Queries via ORM ou parâmetros vinculados — SQL concatenado é proibido.
- Logs nunca contêm tokens, senhas, e-mails completos ou coordenadas precisas de usuários.
- Geolocalização do navegador somente mediante permissão explícita.
- Dependências verificadas (pip-audit, npm audit) no CI.

## 6. Qualidade e testes

- Toda funcionalidade tem critérios de aceite Given/When/Then.
- Cobertura mínima: **80% em `services/`, `risk/`, `simulation/` e `ingestion/`**; demais módulos sem meta numérica, mas com testes dos caminhos críticos.
- Adapters de fontes externas são testados com respostas gravadas (fixtures marcadas como `test_data`), nunca contra a fonte real no CI.
- Bug corrigido = teste de regressão.
- Testes não podem ser ignorados ou desativados para "fazer passar".

## 7. Política de dados reais e simulados (inegociável)

Todo registro de dado carrega:

| Campo | Valores |
|---|---|
| `source_id` | referência a `data_sources` |
| `kind` | `OBSERVED` · `FORECAST` · `MODELED` · `DERIVED` · `SIMULATED` |
| `mode` | `REAL` · `SIMULATION` · `HYBRID` |
| `observed_at` / `valid_at` | UTC |
| `ingested_at` | UTC |
| `quality_flag` | `OK` · `SUSPECT` · `FAILED` · `UNCHECKED` |
| unidade | explícita no schema |

Regras:
1. Nenhuma substituição silenciosa: se a fonte primária falha, o dado aparece como indisponível, não é trocado por outro.
2. Dado de previsão/modelo **nunca** é exibido como observação.
3. Dado simulado sempre tem identificação visual persistente e nunca é gravado nas tabelas de observação real.
4. Frescor é calculado na leitura (`FRESH`, `DELAYED`, `STALE`, `UNAVAILABLE`, `UNKNOWN`), com limites configuráveis por fonte.
5. Dados brutos relevantes são preservados (`raw_payloads`) antes de normalização; correções são auditáveis.
6. Fixtures de teste nunca são carregadas em ambiente de produção (guarda no seed por `APP_ENV`).
7. **Alertas oficiais**, **alertas meteorológicos**, **risco estimado pelo sistema**, **alertas de qualidade de dados** e **alertas de simulação** são categorias distintas, com rótulos distintos na UI.

## 8. Estrutura de dados

- Armazenamento sempre em **UTC**; conversão para `America/Sao_Paulo` só na apresentação.
- Geometrias em **SRID 4326 (WGS84)** para armazenamento e intercâmbio; cálculos métricos em **SIRGAS 2000 / UTM 23S (EPSG:31983)** quando necessário.
- Unidades canônicas: temperatura °C, precipitação mm, pressão hPa, vento m/s (conversão para km/h na UI, com unidade exibida), umidade %, nível de rio cm.
- Migrations obrigatórias (Alembic); nunca alterar schema manualmente.
- Tabelas só são criadas quando uma spec aprovada precisa delas.

## 9. Convenções de nomenclatura

| Item | Convenção | Exemplo |
|---|---|---|
| Tabelas | snake_case, plural | `weather_observations` |
| Colunas de tempo | sufixo `_at` | `observed_at` |
| Python | snake_case; classes PascalCase | `InmetAdapter` |
| TS/React | componentes PascalCase; hooks `useX` | `StationCard`, `useCurrentWeather` |
| Rotas API | kebab/plural, versionadas | `/api/v1/stations/{id}/observations` |
| Requisitos | `FR-NNN`, `NFR-NNN`, `BR-NNN`, `AC-NNN` | `FR-012` |
| Tarefas | `TNNN` por spec | `T004` |
| Specs | `specs/NNN-nome/` | `specs/002-weather-ingestion/` |
| ADRs | `docs/architecture/adr/ADR-NNN-titulo.md` | `ADR-003-inmet-primary-source.md` |

### 9.1 Idioma
- **Em português:** documentação, specs, ADRs, comentários e docstrings, textos da interface, mensagens de erro e de validação da API, títulos e descrições do OpenAPI, nomes das etapas do CI, mensagens de commit e descrições de PR.
- **Em inglês (convenção técnica):** identificadores de código (funções, classes, variáveis), nomes de arquivos de código, tabelas e colunas, rotas da API, chaves de JSON e nomes de eventos de log.

## 10. Regras de integração

- Uma fonte = um adapter em `backend/app/integrations/<fonte>/`, sem regra de risco nem formatação.
- Antes de escrever um adapter: registro completo em `docs/data-sources/SOURCES.md` e smoke test real.
- Timeouts explícitos, retry com backoff exponencial e jitter, circuit breaker por fonte, rate limit respeitando termos.
- Ingestão idempotente (chave natural: `source_id + station_id + observed_at + variable`).
- Falha em uma fonte não derruba as demais; cada execução grava `ingestion_runs`.
- Scraping só como último recurso, com termos de uso verificados e registrados em ADR.
- Atribuição de licença (ex.: CC BY 4.0) exibida na UI e nos relatórios.

## 11. Padrões UX/UI

- Hierarquia: o que está acontecendo → onde → o que pode acontecer → confiabilidade.
- Progressive disclosure: usuário cotidiano vê o essencial; análise avançada fica a um clique.
- Todo componente de dados implementa os estados: `loading`, `success`, `empty`, `error`, `offline`, `degraded`, `stale`, `partial`, `simulation`.
- Cores de risco: verde (baixo), amarelo (moderado), laranja (alto), vermelho (crítico), cinza (desconhecido) — **sempre** acompanhadas de texto e ícone.
- WCAG 2.2 AA como meta; reduced motion respeitado.
- Proibido: neon, glassmorphism indiscriminado, KPIs sem fonte, botões sem ação, filtros que não filtram.
- Contexto (local, período, camadas, modo) persistido na URL quando compartilhável.

## 12. Versionamento

- Git com commits pequenos no padrão Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`).
- Branch por funcionalidade (`feat/002-weather-ingestion`); `main` sempre executável.
- SemVer para releases; versão do motor de risco e do motor de simulação versionadas independentemente (`risk_engine_version`, `simulation_engine_version`).
- Nenhuma mudança destrutiva sem autorização explícita do responsável.

## 13. Limitações científicas e operacionais

- O motor de risco v1 é **heurístico, experimental e não validado**. A UI e os relatórios dizem isso explicitamente.
- Coeficientes provisórios são marcados `experimental`, com origem documentada e configuráveis.
- Não se tiram conclusões sobre mudança climática a partir de séries curtas (< 30 anos para normais climatológicas).
- O DEM disponível (Copernicus GLO-30) é de superfície e tem resolução de 30 m: insuficiente para microdrenagem urbana.
- A cobertura de estações é esparsa; interpolação espacial é uma estimativa e é rotulada como `DERIVED`.
- Fontes sem API pública (CEMADEN, CGE, SACE) limitam a atualização automática; isso é exibido no painel de saúde das fontes.

## 14. Processo (Spec-Driven Development)

Constituição → Spec → Plan → Tasks → Implementação → Testes → Revisão → Aprovação → próxima etapa.

- **DoR:** objetivo, escopo, critérios de aceite, dependências e contexto definidos; sem ambiguidade crítica.
- **DoD:** spec atendida, critérios verificados, testes passando, sem regressão conhecida, documentação e `CURRENT_STATUS.md` atualizados, estados de erro/vazio tratados, fontes identificadas.
- Mudança de escopo: registrar → avaliar impacto → atualizar spec/plan/tasks → só então implementar.
- Rastreabilidade: `FR → T → arquivo → teste → AC`, mantida na seção "Traceability" de cada `tasks.md`.

## 15. Alterações desta constituição

| Versão | Data | Mudança | Motivo |
|---|---|---|---|
| 1.0.0 | 2026-11-19 | Criação | Fase 0 |
| 1.1.0 | 2026-11-19 | §9.1 Idioma: todo texto legível do projeto em português | Pedido do responsável |
| 1.2.0 | 2026-11-19 | §3: MapLibre GL substitui React Leaflet | Mapa 2D/3D a pedido do responsável (ADR-009) |
