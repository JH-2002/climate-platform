# Plan 005 — Motor de risco de alagamento v0

## Decisões
- **ADR-010:** GeoSampa (WFS aberto) é a fonte de suscetibilidade e de ocorrências. O motor v0 é uma matriz de regras explicável (nível de chuva × suscetibilidade), no lugar de um índice contínuo ponderado.
  - **Por quê:** cada resultado tem que ser explicável em uma frase, e ainda não há dados para calibrar pesos.
- Ingestão das camadas pelo mesmo pipeline das fases 2–4: `ingestion_runs`, `raw_payloads` com hash e circuit breaker. A projeção é pedida em EPSG:4326 (`srsName`) para evitar conversão local.
- O motor fica em `app/risk/` (módulo previsto na ARCHITECTURE.md). Ele não importa adaptadores nem a API; recebe dataclasses e devolve dataclasses. Isso é verificado no contrato do import-linter.

## Modelo de dados (migration `0003_flood_risk`)
| Tabela | Conteúdo | Chave natural |
|---|---|---|
| `hydro_risk_sectors` | `source_code` (ex.: `HPI-01-01`), área, nome, grau (1–4), tipos de processo, moradias, subprefeitura, bacia, `inspected_at`, `geom` MultiPolygon 4326, `in_flood_extent_100y` (derivado), `synced_at` | `source_id + source_code` |
| `flood_extent_areas` | período de retorno, `geom` | `source_id + source_code` |
| `flood_occurrences` | tipo (`ALAGAMENTO`/`INUNDACAO`), `occurred_on`, subprefeitura, `geom` Point | `source_id + layer + source_code` |
| `risk_runs` | `engine_version`, `computed_at`, `valid_until`, `forecast_issued_at`, `forecast_freshness`, `params` (jsonb), `status`, `sector_count` | id |
| `risk_assessments` | `run_id`, `sector_id`, `category`, `rain_level`, `susceptibility`, `p1h_max_mm`, `p24_mm`, `a72_mm`, `forecast_point_key`, `factors` (jsonb), `nearby_occurrences_12m` | `run_id + sector_id` |

Índices GiST em todas as geometrias. Seeds em `data_sources`: `geosampa-risk-sectors`, `geosampa-flood-extent`, `geosampa-flood-occurrences`, `flood-risk-engine` (fonte do tipo DERIVED, para o painel de saúde).

## Backend
| Arquivo | Responsabilidade |
|---|---|
| `integrations/geosampa/wfs.py` | URL e parâmetros do `GetFeature` (JSON, EPSG:4326); parse puro de cada camada; normalização de tipos de processo |
| `ingestion/jobs.py` | Jobs `geosampa_sync` (diário, as três camadas na mesma execução, uma `ingestion_run` por camada) |
| `services/flood_layers.py` | Upserts e derivados: `in_flood_extent_100y` (`ST_Intersects`), contagem de ocorrências a até 300 m em 12 meses (`ST_DWithin` em geography) |
| `risk/rules.py` | `rain_level`, `susceptibility`, `category`, `explain`. Coeficientes em `risk/coefficients.py` (`ENGINE_VERSION = "0.1.0-experimental"`) |
| `risk/engine.py` | `assess(sectors, rain_by_point, freshness, now) -> RunResult`. Puro |
| `services/risk.py` | Monta entradas (setor → ponto mais próximo; `P1h_max`, `P24`, `A72` a partir de `weather_forecasts`), roda o motor e grava `risk_runs` e `risk_assessments` numa transação; consultas da API |
| `api/v1/risk.py` | `/risk/summary`, `/risk/areas`, `/risk/areas/{id}` |
| `api/v1/maps.py` | `/map/layers/risk`, `/map/layers/flood-occurrences` |
| `workers/tasks/risk.py` | `compute_flood_risk`, encadeada depois de `ingest_open_meteo_forecast` e também no `beat_init` |
| `integrations/open_meteo/forecast.py` | `past_days=3`. Horas anteriores à coleta são gravadas, mas tratadas como `MODELED` na leitura (`valid_at < issued_at`) |
| `core/config.py` | Padrão de `FORECAST_POINTS` com grade 3×4 sobre o bbox da capital; `GEOSAMPA_WFS_URL` |

## Frontend
| Arquivo | Responsabilidade |
|---|---|
| `features/risk/{types,api,hooks,categories}.ts` | Tipos, chamadas e textos/cores das categorias (com ícone e texto, Constituição §11) |
| `components/risk/RiskDisclaimer.tsx` | Faixa fixa "Estimativa experimental… não é alerta oficial… 199" |
| `components/risk/RiskSummary.tsx`, `RiskTable.tsx`, `RiskExplanation.tsx` | Resumo, ranking filtrável e explicação dos fatores |
| `app/risk/page.tsx` | Página `/risk` com filtros na URL |
| `components/map/*` | Camadas `risco` (fill/fill-extrusion) e `ocorrencias`, legenda e popups |
| `components/weather/*` | Cartão "Risco estimado aqui" no painel do clima |
| `features/navigation/registry.ts` | Item "Risco" |

## Testes
- **Unitários (motor):** matriz completa (16 combinações), limites das faixas, bônus de `A72` e de suscetibilidade, "desconhecido" (BR-063), determinismo, e frases dos fatores (AC-061, AC-062).
- **Unitários (adaptador):** parse das respostas reais gravadas do GeoSampa (recortes pequenos de cada camada) e normalização de tipos com acento e quebra de linha.
- **Integração:** sincronização idempotente (AC-060); derivados espaciais; execução do motor com previsão gravada; rotas da API; previsão `STALE` → desconhecido (AC-063).
- **Frontend:** categorias e textos, faixa de aviso, tabela e filtros, ausência da palavra "alerta" nos rótulos de risco (AC-067).
- **Navegador real:** camada de risco em 2D e 3D, popup e página `/risk` (AC-064, AC-065).

## Ordem
T050 → T051 → T052 → T053 → T054 → T055 → T056 → T057 → T058 → T059 → T060 → T061.
