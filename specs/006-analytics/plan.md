# Plan 006 — Análises

## Decisões
- **ADR-011:**
  - Séries de referência: chuva mensal medida do IAG/USP (1933–2025) e reanálise diária da Open-Meteo (1991 até ontem).
  - Insights só por regras documentadas, sem texto gerado por IA.
  - Sem séries longas, os itens 13.3, 13.6 e 13.9 do documento mestre não teriam base.
- **Catálogo declarativo:** cada conjunto de dados é descrito em `analytics/catalog.py` (metadados, variáveis, agregações permitidas, visualizações compatíveis), e as rotas e o Studio leem dele. Nada de métrica fixa na interface.
- **Onde agregar:** PostgreSQL (`date_trunc`, `percentile_cont`) para volume; Python puro para regras, climatologia e estatísticas de amostras já reduzidas.

## Modelo de dados (migration `0004_analytics`)
| Tabela | Conteúdo | Chave natural |
|---|---|---|
| `climate_daily` | reanálise diária: `point_key`, `point` (geography), `cell_key` (célula devolvida pela fonte), `day` (date local), `variable`, `value`, `unit`, `kind = 'MODELED'`, `raw_payload_id`, `ingested_at` | `source_id + point_key + day + variable` |
| `rain_monthly_observed` | IAG/USP: `station_code`, `year`, `month`, `value_mm`, `kind = 'OBSERVED'`, `source_file`, `file_hash` | `source_id + station_code + year + month` |
| `published_normals` | normais publicadas (para conferência): período, mês (0 = anual), valor | `source_id + station_code + period + month` |
| `backfill_progress` | carga inicial por ponto: último dia carregado, estado | `source_id + point_key` |

Seeds em `data_sources`:
- `open-meteo-archive` (diária; intervalo 86400);
- `iag-usp-rain-monthly` (anual; intervalo 400 dias; atualização manual).

## Backend
| Arquivo | Responsabilidade |
|---|---|
| `integrations/open_meteo/archive.py` | Parâmetros e parse da Historical API (diária, fuso local) |
| `integrations/iag/monthly_table.py` | Parse do texto da tabela da Prefeitura (vírgula decimal, ponto de milhar) e conferência mês × total |
| `scripts/extract_iag_table.py` | Extrai o texto da página salva e gera `data/reference/iag_usp_chuva_mensal_1933_2025.csv` + metadados |
| `ingestion/archive_jobs.py` | Carga inicial com retomada (um ponto por execução de tarefa) e atualização dos últimos 10 dias |
| `ingestion/reference_import.py` | Importa o CSV do IAG e as normais publicadas |
| `analytics/stats.py` | `describe`, percentis (método linear), IQR, atípicos, cobertura |
| `analytics/climatology.py` | Normais mensais, percentis por mês, sequências secas, anomalia proporcional, média móvel |
| `analytics/catalog.py` | Conjuntos, variáveis, unidades, tipos, agregações e visualizações permitidas |
| `analytics/rules.py` | IN-01 a IN-06 (BR-080), puras, com limites versionados (`INSIGHT_RULES_VERSION`) |
| `services/analytics.py` | Consultas agregadas, montagem de KPIs e insights, CSV |
| `api/v1/analytics.py` | `/analytics/datasets`, `/datasets/{id}/describe`, `/kpis`, `/insights`, `/series`, `/series.csv`, `/climatology`, `/sources-health`, `/risk-history` |
| `workers/tasks/analytics.py` | `ingestion.open_meteo_archive` (diária) e `ingestion.open_meteo_archive_backfill` (até completar) |

O import-linter ganha a regra "`app.analytics` é puro", como `app.risk`.

## Frontend
| Arquivo | Responsabilidade |
|---|---|
| `features/analytics/*` | Tipos, chamadas, estado do Studio ↔ URL, compatibilidade de visualizações (pura) |
| `components/overview/*` | Painel executivo: Agora, Atenção (insights), Onde, Confiabilidade, KPIs |
| `components/analytics/*` | Gráficos (Recharts) com tabela alternativa e nota de fonte; abas Chuva, Tendências, Risco, Fontes; Studio; fichas do Explorer |
| `app/page.tsx` | Visão geral = painel executivo |
| `app/analytics/page.tsx`, `app/analytics/datasets/page.tsx` | Áreas de análise e Data Explorer |

## Testes
- **Unitários:**
  - estatísticas contra valores calculados à mão;
  - climatologia e sequências secas;
  - cada regra de insight nos dois lados do limite;
  - catálogo (agregações e visualizações proibidas);
  - parse da tabela do IAG (somas e normais = AC-080);
  - parse da reanálise com resposta real gravada.
- **Integração:**
  - importação idempotente;
  - carga com retomada;
  - `series`, `describe`, `climatology`, `kpis`, `insights` e CSV com dados gravados;
  - 422 para agregação incompatível.
- **Frontend:** estado do Studio na URL, lista de visualizações por conjunto, KPIs com fonte, tabelas alternativas, axe.
- **Navegador real:** Visão geral, abas e Studio com a carga real.

## Ordem
- **Parte A:** T070 → T079 (validada no navegador antes de começar a B).
- **Parte B:** T080 → T087.
