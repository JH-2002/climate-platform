# Tasks 005 — Motor de risco de alagamento v0

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T050 | Gravar respostas reais do GeoSampa (recortes) como fixtures | `tests/fixtures/geosampa_*` | Arquivos com data, camada e URL | — | [ ] |
| T051 | Adaptador WFS do GeoSampa (parâmetros e parse) | `integrations/geosampa/wfs.py` | FR-060 | `test_geosampa_wfs.py` | [ ] |
| T052 | Migration `0003_flood_risk` e tabelas | `migrations/`, `models/tables.py` | Upgrade e downgrade no CI | integração | [ ] |
| T053 | Job de sincronização e derivados espaciais | `ingestion/jobs.py`, `services/flood_layers.py`, `workers/` | AC-060 | `test_flood_sync.py` | [ ] |
| T054 | Grade de previsão e `past_days=3` | `core/config.py`, `open_meteo/forecast.py` | FR-062 | unitários existentes ajustados | [ ] |
| T055 | Regras e coeficientes do motor | `risk/rules.py`, `risk/coefficients.py` | BR-060 a BR-063 | `test_risk_rules.py` | [ ] |
| T056 | Motor puro e explicações | `risk/engine.py` | AC-061, AC-062, AC-066 | `test_risk_engine.py` | [ ] |
| T057 | Serviço, gravação das execuções e tarefa Celery | `services/risk.py`, `workers/tasks/risk.py` | FR-064, AC-063 | `test_risk_service.py` | [ ] |
| T058 | API de risco e camadas de mapa | `api/v1/risk.py`, `api/v1/maps.py` | FR-065 a FR-068 | `test_risk_api.py` | [ ] |
| T059 | Página `/risk`, aviso e navegação | `app/risk`, `components/risk`, `features/risk` | FR-070, AC-064, AC-067 | `risk.test.tsx` | [ ] |
| T060 | Camadas no mapa e cartão no painel do clima | `components/map`, `components/weather` | FR-069, FR-071, AC-065 | `map-ui.test.tsx` | [ ] |
| T061 | Validação no navegador e documentação | docs, SOURCES, ADR-010 | 2D/3D e `/risk` verificados com dados reais | manual | [ ] |
