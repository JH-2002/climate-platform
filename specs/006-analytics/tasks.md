# Tasks 006 — Análises

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — base analítica e visão geral

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T070 | Extrair a tabela do IAG/USP e gravar o CSV de referência + normais publicadas | `scripts/extract_iag_table.py`, `data/reference/` | Somas conferidas nos 93 anos | `test_iag_table.py` | [x] |
| T071 | Gravar resposta real da reanálise (recorte) como fixture | `tests/fixtures/` | Arquivo com data, ponto e URL | — | [x] |
| T072 | Adaptadores: reanálise e tabela do IAG | `integrations/open_meteo/archive.py`, `integrations/iag/` | FR-080, FR-081 | unitários | [x] |
| T073 | Migration `0004_analytics` e tabelas | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [x] |
| T074 | Importação do IAG e ingestão da reanálise (carga com retomada + atualização diária) | `ingestion/`, `workers/` | AC-080, AC-081, NFR-082 | integração | [x] |
| T075 | Motor analítico puro: estatísticas, climatologia, catálogo | `analytics/stats.py`, `climatology.py`, `catalog.py` | AC-082 | unitários | [x] |
| T076 | Regras de insight IN-01 a IN-06 | `analytics/rules.py` | BR-080, AC-083 | unitários | [x] |
| T077 | Serviço e API: datasets, describe, kpis, insights | `services/analytics.py`, `api/v1/analytics.py` | FR-082 a FR-085 | integração | [x] |
| T078 | Painel executivo na Visão geral | `app/page.tsx`, `components/overview/` | FR-086, AC-084 | `overview.test.tsx` | [x] |
| T079 | Validação da Parte A com a carga real e documentação | docs | Navegador + CI | manual | [x] |

## Parte B — áreas de análise

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T080 | `series`, `climatology`, CSV | `services/analytics.py`, `api/v1/analytics.py` | FR-087 a FR-089, AC-085, AC-087 | integração | [x] |
| T081 | Aba Chuva | `components/analytics/rain/*` | FR-090 | `analytics.test.tsx` | [x] |
| T082 | Aba Tendências | `components/analytics/trends/*` | FR-091, AC-088 | idem | [x] |
| T083 | Aba Risco (histórico) | `components/analytics/risk/*`, rota `risk-history` | FR-092 | idem | [x] |
| T084 | Aba Fontes e dados | `components/analytics/sources/*`, rota `sources-health` | FR-093 | idem | [x] |
| T085 | Analytics Studio | `components/analytics/studio/*` | FR-094, AC-086 | `studio.test.tsx` | [x] |
| T086 | Data Explorer | `app/analytics/datasets`, `components/analytics/explorer/*` | FR-095 | idem | [x] |
| T087 | Validação da Parte B e documentação | docs | Navegador + CI | manual | [x] |

## Validação (2026-11-20)
- Parte A: importação do IAG/USP (1.116 meses; normal 1991–2020 calculada = publicada, 1.559,2 mm); carga da reanálise completa em 12 pontos (629.128 registros); Visão geral com KPIs e insights IN-05/IN-06.
- Parte B: abas Chuva, Tendências, Risco, Fontes e dados, Studio (calendário, CSV) e Explorador conferidas no navegador com os dados reais; CI verde.
- Correções da validação: mês em andamento marcado como incompleto e sem comparação com a normal do mês inteiro; ponto central limitado a 10 km; contagem só de pontos de previsão ativos; intervalos longos exibidos em dias; eixos com espaço para os rótulos.
