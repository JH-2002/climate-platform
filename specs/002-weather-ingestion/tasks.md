# Tasks 002 — Ingestão de dados meteorológicos

Legenda: `[ ]` pendente · `[i]` implementada, aguardando CI · `[x]` validada · `[b]` bloqueada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T010 | Tabelas Core + migração 0002 com catálogo de fontes | `models/tables.py`, `migrations/versions/0002_*` | `alembic upgrade head` cria tabelas e índices | integração | [ ] |
| T011 | Cliente HTTP resiliente (timeout, retentativa com backoff + jitter, 204) | `integrations/http.py` | retenta 5xx/429/rede; não retenta 4xx | `test_http.py` | [ ] |
| T012 | Parser da lista de estações INMET + filtro de região | `integrations/inmet/stations.py` | fixture real → A701 e A771 na capital; status mapeado | `test_inmet_stations.py` | [ ] |
| T013 | URL e parser da previsão Open-Meteo (unidades, fuso → UTC) | `integrations/open_meteo/forecast.py` | fixture real → 672 pontos horários + 28 diários; km/h → m/s | `test_open_meteo.py` | [ ] |
| T014 | Frescor (BR-020) e circuit breaker | `services/freshness.py`, `ingestion/pipeline.py` | tabelas de casos | `test_freshness.py`, `test_circuit.py` | [ ] |
| T015 | Pipeline: runs, payload bruto com deduplicação, contagens, erros redigidos | `ingestion/pipeline.py` | FR-023, FR-024 | integração | [ ] |
| T016 | Jobs: sincronizar estações (upsert, `INACTIVE`) e previsão (upsert) | `ingestion/jobs.py` | FR-021, FR-025, FR-029 | integração | [ ] |
| T017 | Tarefas Celery + agenda no beat | `workers/tasks/ingestion.py`, `celery_app.py` | tarefas registradas; rodam no início do beat | unit | [ ] |
| T018 | API `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations` | `api/v1/*`, `services/*` | FR-030, FR-031; AC-021, AC-024 | integração | [ ] |
| T019 | Saúde das fontes no `/status` (FR-032) | `frontend/features/sources`, `components/system/SourcesView.tsx` | todos os estados, axe | `SourcesView.test.tsx` | [ ] |
| T020 | Adaptador de observações horárias do INMET | `integrations/inmet/observations.py` | resposta real gravada com token; AC-022 | — | [b] token |
| T021 | Validação local: coletas reais rodando no Docker | — | estações e previsão gravadas; `/status` mostra fontes `FRESH` | manual | [ ] |
| T022 | Documentação e `CURRENT_STATUS.md` | docs | DoD | — | [ ] |

## Rastreabilidade
| Requisito | Tarefas | Teste | Aceite |
|---|---|---|---|
| FR-020 | T010 | integração (catálogo) | — |
| FR-021 | T012, T016 | `test_inmet_stations.py`, integração | — |
| FR-022, FR-026, FR-027 | T020 | — | AC-022 (bloqueado) |
| FR-023, FR-024 | T015 | integração | — |
| FR-025 | T016 | integração | AC-020 |
| FR-028 | T014, T018 | integração | AC-021 |
| FR-029 | T013, T016 | `test_open_meteo.py`, integração | — |
| FR-030 | T014, T018 | `test_freshness.py`, integração | AC-021 |
| FR-031 | T018 | integração | AC-024 |
| FR-032 | T019 | `SourcesView.test.tsx` | — |
| NFR-020 | T011, T014 | `test_http.py`, `test_circuit.py`, integração | AC-023 |
| NFR-022 | T015 | `test_redaction.py`, integração | — |
