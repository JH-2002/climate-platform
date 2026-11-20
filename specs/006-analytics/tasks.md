# Tasks 006 — Análises

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — base analítica e visão geral

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T070 | Extrair a tabela do IAG/USP e gravar o CSV de referência + normais publicadas | `scripts/extract_iag_table.py`, `data/reference/` | Somas conferidas nos 93 anos | `test_iag_table.py` | [ ] |
| T071 | Gravar resposta real da reanálise (recorte) como fixture | `tests/fixtures/` | Arquivo com data, ponto e URL | — | [ ] |
| T072 | Adaptadores: reanálise e tabela do IAG | `integrations/open_meteo/archive.py`, `integrations/iag/` | FR-080, FR-081 | unitários | [ ] |
| T073 | Migration `0004_analytics` e tabelas | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [ ] |
| T074 | Importação do IAG e ingestão da reanálise (carga com retomada + atualização diária) | `ingestion/`, `workers/` | AC-080, AC-081, NFR-082 | integração | [ ] |
| T075 | Motor analítico puro: estatísticas, climatologia, catálogo | `analytics/stats.py`, `climatology.py`, `catalog.py` | AC-082 | unitários | [ ] |
| T076 | Regras de insight IN-01 a IN-06 | `analytics/rules.py` | BR-080, AC-083 | unitários | [ ] |
| T077 | Serviço e API: datasets, describe, kpis, insights | `services/analytics.py`, `api/v1/analytics.py` | FR-082 a FR-085 | integração | [ ] |
| T078 | Painel executivo na Visão geral | `app/page.tsx`, `components/overview/` | FR-086, AC-084 | `overview.test.tsx` | [ ] |
| T079 | Validação da Parte A com a carga real e documentação | docs | Navegador + CI | manual | [ ] |

## Parte B — áreas de análise

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T080 | `series`, `climatology`, CSV | `services/analytics.py`, `api/v1/analytics.py` | FR-087 a FR-089, AC-085, AC-087 | integração | [ ] |
| T081 | Aba Chuva | `components/analytics/rain/*` | FR-090 | `analytics.test.tsx` | [ ] |
| T082 | Aba Tendências | `components/analytics/trends/*` | FR-091, AC-088 | idem | [ ] |
| T083 | Aba Risco (histórico) | `components/analytics/risk/*`, rota `risk-history` | FR-092 | idem | [ ] |
| T084 | Aba Fontes e dados | `components/analytics/sources/*`, rota `sources-health` | FR-093 | idem | [ ] |
| T085 | Analytics Studio | `components/analytics/studio/*` | FR-094, AC-086 | `studio.test.tsx` | [ ] |
| T086 | Data Explorer | `app/analytics/datasets`, `components/analytics/explorer/*` | FR-095 | idem | [ ] |
| T087 | Validação da Parte B e documentação | docs | Navegador + CI | manual | [ ] |
