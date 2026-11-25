# Tasks 005 — Motor de risco de alagamento v0

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T050 | Gravar respostas reais do GeoSampa (recortes) como fixtures | `tests/fixtures/geosampa_*` | Arquivos com data, camada e URL | — | [x] |
| T051 | Adaptador WFS do GeoSampa (parâmetros e parse) | `integrations/geosampa/wfs.py` | FR-060 | `test_geosampa_wfs.py` | [x] |
| T052 | Migration `0003_flood_risk` e tabelas | `migrations/`, `models/tables.py` | Upgrade e downgrade no CI | integração | [x] |
| T053 | Job de sincronização e derivados espaciais | `ingestion/jobs.py`, `services/flood_layers.py`, `workers/` | AC-060 | `test_flood_sync.py` | [x] |
| T054 | Grade de previsão e `past_days=3` | `core/config.py`, `open_meteo/forecast.py` | FR-062 | unitários existentes ajustados | [x] |
| T055 | Regras e coeficientes do motor | `risk/rules.py`, `risk/coefficients.py` | BR-060 a BR-063 | `test_risk_rules.py` | [x] |
| T056 | Motor puro e explicações | `risk/engine.py` | AC-061, AC-062, AC-066 | `test_risk_engine.py` | [x] |
| T057 | Serviço, gravação das execuções e tarefa Celery | `services/risk.py`, `workers/tasks/risk.py` | FR-064, AC-063 | `test_risk_service.py` | [x] |
| T058 | API de risco e camadas de mapa | `api/v1/risk.py`, `api/v1/maps.py` | FR-065 a FR-068 | `test_risk_api.py` | [x] |
| T059 | Página `/risk`, aviso e navegação | `app/risk`, `components/risk`, `features/risk` | FR-070, AC-064, AC-067 | `risk.test.tsx` | [x] |
| T060 | Camadas no mapa e cartão no painel do clima | `components/map`, `components/weather` | FR-069, FR-071, AC-065 | `map-ui.test.tsx` | [x] |
| T061 | Validação no navegador e documentação | docs, SOURCES, ADR-010 | 2D/3D e `/risk` verificados com dados reais | manual | [x] |

## Validação (2026-11-19/20)

- CI verde em `885db40`, `a215d71` e `1367ba1` (192+ testes no backend, com PostGIS real; lint, tipagem e testes no frontend).
- Docker local, dados reais: as três camadas do GeoSampa sincronizadas (793 setores, 53 manchas, 630 ocorrências); a primeira execução do motor gravou 793 avaliações, todas "baixo" numa noite sem chuva prevista relevante (máx. 1,5 mm/h).
- Os derivados batem com o cálculo independente feito no navegador sobre as mesmas camadas: 58 setores cruzam mancha de 100 anos e 164 têm 2 ou mais ocorrências a até 300 m.
- Camada de risco no mapa: 484 KB, 93 ms (NFR-062).
- Verificado no navegador: `/risk` (aviso, resumo, filtros, tabela, explicação do setor HMP-30-02 com 6 ocorrências), mapa 2D (popup do setor) e 3D (setores extrudados e ocorrências), cartão no painel do clima.

Problemas encontrados e corrigidos na validação:
- Ponto de previsão antigo (de antes da grade) continuava sendo usado; pontos sem coleta há mais de 3 h saem do motor, do mapa e do painel (`a215d71`).
- Em 3D, o clique sobre a extrusão no relevo não era detectado; o preenchimento fica quase transparente por baixo e recebe o clique (`1367ba1`).
