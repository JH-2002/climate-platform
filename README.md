# Climate Intelligence Platform

Plataforma web de monitoramento meteorológico, análise geoespacial, estimativa de condições favoráveis a alagamentos, simulação de cenários e relatórios — construída com dados reais, rastreáveis e com limitações declaradas.

> **Estado:** Fases 0–7 concluídas. Coleta automática de estações do INMET, previsão da Open-Meteo e camadas de risco do GeoSampa; painel do clima em http://localhost:3000/weather, mapa 2D/3D em http://localhost:3000/map e risco de alagamento estimado (experimental, não é alerta oficial) em http://localhost:3000/risk; análises e painel executivo em http://localhost:3000/analytics e na Visão geral; laboratório de simulação em http://localhost:3000/simulation; geointeligência (Fase 8, Parte A) em http://localhost:3000/geo-3d. Observações medidas do INMET aguardam token. Veja [CURRENT_STATUS.md](CURRENT_STATUS.md).

## Região piloto
Município de São Paulo, com expansão para a RMSP ([ADR-002](docs/architecture/adr/ADR-002-pilot-region-sao-paulo.md)).

## Arquitetura
Monólito modular FastAPI + workers Celery + PostgreSQL/PostGIS + Redis + Next.js. Detalhes em [ARCHITECTURE.md](ARCHITECTURE.md).

| Serviço | Porta (host) | Função |
|---|---|---|
| frontend | 3000 | Next.js (App Router) |
| backend | 8000 | API REST `/api/v1`, docs em `/api/docs` |
| worker | — | Celery (processamento em background) |
| beat | — | Agendador Celery |
| db | **5433** | PostgreSQL 16 + PostGIS 3.4 (5433 para não conflitar com um PostgreSQL local) |
| redis | 6379 | Broker e cache |

## Pré-requisitos
- **Docker Desktop** com backend WSL2 (Windows) ou Docker Engine (Linux).
- Python ≥ 3.11 apenas para rodar `scripts/smoke_sources.py` fora do Docker (opcional).

## Executar
```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
docker compose up -d --build
docker compose ps             # todos os serviços devem ficar "healthy" (até ~3 min)
```
- Frontend: http://localhost:3000 — página de estado: http://localhost:3000/status
- API: http://localhost:8000/api/v1/health/ready — OpenAPI: http://localhost:8000/api/docs

O `frontend/package-lock.json` é versionado e gerado pelo workflow **Gerar lockfiles** (Actions), com o mesmo Node da imagem. Ao mudar dependências do frontend, rode o workflow de novo ou, localmente, `docker compose run --rm frontend npm install` (grava o lock na pasta montada).

## Testes
```bash
# Backend: unitários + integração (com banco, Redis e worker reais)
docker compose exec -e RUN_INTEGRATION=1 backend pytest --cov=app

# Qualidade backend
docker compose exec backend ruff format .
docker compose exec backend ruff check .
docker compose exec backend mypy app
docker compose exec backend lint-imports

# Frontend
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run format

# Smoke test das fontes externas (na máquina host, sem dependências)
python scripts/smoke_sources.py
```

## Validação da Fase 1 (roteiro)
| # | Verificação | Critério |
|---|---|---|
| 1 | `docker compose ps` | 6 serviços `healthy` (AC-001) |
| 2 | `GET /api/v1/health/ready` | 200, `db`, `postgis`, `redis`, `worker` = `ok` (AC-002) |
| 3 | `docker compose stop redis` e repetir 2 | 503, `redis: unavailable`, demais com estado real (AC-003); depois `docker compose start redis` |
| 4 | `curl -i -H "X-Correlation-ID: abc" localhost:8000/api/v1/nope` | 404 `application/problem+json` com `correlation_id: "abc"`; `docker compose logs backend` mostra o mesmo id (AC-004) |
| 5 | `docker compose stop backend` e abrir `/status` | mensagem de erro + "Tentar novamente" (AC-005) |
| 6 | Remover `DATABASE_URL` do `.env` e `docker compose up backend` | sai com log `missing_required_setting` (AC-007) |
| 7 | `python scripts/smoke_sources.py` | gera `docs/data-sources/smoke-results.md` (AC-008) |
| 8 | Push para o GitHub | CI verde (AC-006) |

## Documentos
| Arquivo | Função |
|---|---|
| [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md) | Regras permanentes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Visão técnica global |
| [ROADMAP.md](ROADMAP.md) | Fases |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | Estado atual e bloqueios |
| [DECISIONS.md](DECISIONS.md) | Índice de ADRs |
| [docs/data-sources/SOURCES.md](docs/data-sources/SOURCES.md) | Fontes de dados |
| [specs/](specs/) | Especificações, planos e tarefas |

## Metodologia
Spec-Driven Development: Constituição → Spec → Plan → Tasks → Implementação → Testes → Revisão.

## Fontes e atribuições
Previsão: Open-Meteo.com (CC BY 4.0). Observações: INMET. Elevação: Produced using Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA, all rights reserved. Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo.

## Configuração da região
`REGION_BBOX` (lon_min,lat_min,lon_max,lat_max) define quais estações são sincronizadas e `FORECAST_POINTS` (lat,lon;lat,lon) define os pontos de previsão. Padrão: município de São Paulo.

## Limitações atuais
- Observações horárias do INMET dependem de token (pedido em andamento).
- Sem autenticação: a API é somente leitura e os locais salvos ficam no navegador (ADR-008).
