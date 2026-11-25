# Tasks 003 — Painel do clima

> Validação (2026-11-19): CI verde no commit `2b833b4` e página `/weather` verificada no Docker local com dados reais (agora 30,8 °C estimado; chuva prevista 4,1 mm em 72 h; estações A701 a 6,2 km e A771 a 19,8 km).

Legenda: `[ ]` pendente · `[i]` implementada, aguardando CI · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T030 | Funções puras de previsão: hora corrente, pivot, acumulados | `services/forecast.py` | BR-040, BR-041; AC-042 | `test_forecast_service.py` | [x] |
| T031 | Consulta do ponto mais próximo e séries | `services/forecast.py` | FR-040 a FR-043 | integração | [x] |
| T032 | Endpoint `/weather/forecast` com relógio injetável | `api/v1/weather.py` | AC-040, AC-041 | integração | [x] |
| T033 | Store de locais no navegador | `features/locations/*` | AC-043 | `locations.test.ts` | [x] |
| T034 | Componentes do painel (Agora, 48 h, 7 dias, chuva, estações) | `components/weather/*` | FR-041 a FR-047; AC-044 | `weather.test.tsx` | [x] |
| T035 | Página `/weather`, local na URL, navegação | `app/weather/page.tsx`, `registry.ts` | FR-045, FR-048; AC-045 | `weather.test.tsx` | [x] |
| T036 | Recharts + lockfile atualizado | `package.json`, `package-lock.json` | `npm ci` no CI | CI | [x] |
| T037 | Validação local e documentação | docs | página verificada com dados reais | manual | [x] |
