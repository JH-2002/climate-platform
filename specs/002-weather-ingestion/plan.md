# Plan 002 — Ingestão de dados meteorológicos

> Status: **Aprovado** (2026-11-19) · Spec: [spec.md](spec.md)

## Ajustes de escopo a partir do smoke test (2026-11-19)
- **Observações horárias do INMET ficam bloqueadas** até o token chegar. A rota sem token respondeu 204, e a constituição (§10) exige uma resposta real antes de escrever o adaptador. A tabela, o endpoint e o estado `UNAVAILABLE / missing_credentials` são entregues agora; o adaptador entra na tarefa T020, quando o token chegar.
- **Lista de estações do INMET** (sem token, testada: 200) e **previsão da Open-Meteo** (testada: 200) são implementadas por completo.
- **FR-032 (nova):** a página `/status` mostra a saúde das fontes (US-010). É a menor interface que dá visibilidade ao trabalho da fase; o dashboard completo continua na spec 003.
- A previsão é pedida com `timezone=America/Sao_Paulo`, para que os agregados diários correspondam ao dia local. O parser converte para UTC usando `utc_offset_seconds`.
- O frescor (BR-020) é calculado pelo horário da última coleta bem-sucedida de cada fonte. A idade da última observação entra junto com o adaptador de observações.

## Componentes novos

| Camada | Arquivo | Responsabilidade |
|---|---|---|
| Modelo | `app/models/tables.py` | Tabelas SQLAlchemy Core (metadata única) |
| Migração | `migrations/versions/0002_ingestion_schema.py` | DDL + catálogo inicial de fontes |
| Integração | `app/integrations/http.py` | GET com timeout, retentativas com backoff exponencial + jitter |
| Integração | `app/integrations/inmet/stations.py` | Parser da lista de estações (sem I/O) |
| Integração | `app/integrations/open_meteo/forecast.py` | URL e parser da previsão (sem I/O) |
| Ingestão | `app/ingestion/pipeline.py` | Execução com `ingestion_runs`, `raw_payloads`, circuit breaker |
| Ingestão | `app/ingestion/jobs.py` | Jobs: sincronizar estações, coletar previsão |
| Serviço | `app/services/freshness.py` | Classificação de frescor (BR-020), função pura |
| Serviço | `app/services/sources.py`, `stations.py` | Consultas para a API |
| API | `app/api/v1/sources.py`, `stations.py` | Endpoints |
| Workers | `app/workers/tasks/ingestion.py` | Tarefas Celery + agenda no beat |
| Frontend | `features/sources/*`, `components/system/SourcesView.tsx` | Saúde das fontes no `/status` |

## Banco de dados (migração 0002)

```
data_sources(id, code UK, name, owner, url, license, attribution, access_method,
             expected_interval_s, requires_credentials, enabled,
             last_attempt_at, last_success_at, last_status, last_error, created_at)
weather_stations(id, source_id FK, external_code, name, state, location geography(Point,4326),
                 altitude_m, status, source_status, started_at, ended_at,
                 first_seen_at, last_seen_at)  UNIQUE(source_id, external_code)  GiST(location)
ingestion_runs(id, source_id FK, started_at, finished_at, status, records_received,
               records_inserted, records_updated, records_rejected, error_summary)
raw_payloads(id, source_id FK, run_id FK, content_hash, request_url, payload jsonb, fetched_at)
             UNIQUE(source_id, content_hash)
weather_observations(id, station_id FK, source_id FK, observed_at, variable, value, unit,
                     kind='OBSERVED', mode='REAL', quality_flag, quality_reason,
                     raw_payload_id FK, ingested_at)  UNIQUE(station_id, variable, observed_at)
weather_forecasts(id, source_id FK, point geography(Point,4326), point_key, resolution,
                  valid_at, variable, value, unit, issued_at, kind='FORECAST', mode='REAL',
                  raw_payload_id FK)  UNIQUE(source_id, point_key, resolution, variable, valid_at)
```
Fontes cadastradas: `inmet-stations` (24 h), `inmet-observations` (1 h, exige token), `open-meteo-forecast` (1 h). A previsão guarda só a emissão mais recente de cada horário (upsert), para o volume não crescer a cada coleta.

## Contratos de API
| Método | Rota | Resposta |
|---|---|---|
| GET | `/api/v1/sources/status` | `{items: [{code, name, owner, license, attribution, freshness, reason, last_success_at, last_attempt_at, last_run_status, expected_interval_s}]}` |
| GET | `/api/v1/stations?bbox=&status=&limit=&offset=` | `{items: [Station], total, limit, offset}` |
| GET | `/api/v1/stations/nearby?lat=&lon=&radius_km=&limit=` | `{items: [Station + distance_km]}` |
| GET | `/api/v1/stations/{id}/observations?from=&to=&variables=` | `{station, items, availability: {freshness, reason}}` |

## Fluxo
Beat → `ingestion.sync_inmet_stations` (24 h) e `ingestion.open_meteo_forecast` (1 h) → worker → `run_ingestion` (circuit breaker → run RUNNING → busca → payload bruto → parse/validação → upsert → contagens → status) → `data_sources.last_*`.

## Estratégia de testes
- Unitários com as **respostas reais gravadas** (`tests/fixtures/*_2026-11-19.json`): parsers, filtro de região, conversão de unidades e fuso, frescor, circuit breaker, retentativas HTTP (`httpx.MockTransport`).
- Integração (PostgreSQL/PostGIS real): idempotência das coletas (AC-020), estação removida vira `INACTIVE`, `nearby` (AC-024), circuit breaker (AC-023), `missing_credentials` (AC-021), endpoints.
- Frontend: `SourcesView` em todos os estados, com axe.

## Segurança
`INMET_TOKEN` nunca é registrado; URLs gravadas em `raw_payloads.request_url` passam por máscara. Mensagens de erro guardadas em `error_summary` passam pela redação de segredos.

## Ordem
T010 → T011 → (T012, T013, T014) → T015 → T016 → T017 → T018 → T019 → T021 → T022.
