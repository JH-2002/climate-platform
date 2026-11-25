# Plan 007 — Laboratório de simulação

## Decisões
- **Reaproveitar o motor de risco** ([ADR-012](../../docs/architecture/adr/ADR-012-simulation-reuses-risk-engine.md)). `app/simulation/` só gera a chuva. A avaliação chama `app.risk.engine.assess`, e cada setor ganha a própria chave de "ponto" (`s:<id>`, distância 0). O motor de risco não muda.
- **Resolução de setor.** A geometria de cada setor vira um ponto interno (`ST_PointOnSurface`), lido uma vez por execução. A distância ao centro da célula usa haversine, já em `services/risk.py`, movido para um módulo puro compartilhado.
- **Cálculo síncrono na API.** Um laço de 100 × 793 avaliações puras leva menos de 1 s. Um worker só acrescentaria fila e acompanhamento. Se o tempo passar de 2 s (NFR-101), a mudança para o worker de simulação previsto na arquitetura fica registrada como alternativa.
- **Aleatoriedade.** `random.Random(seed)`, criado por execução. Cada variação sorteia, nesta ordem, o fator de intensidade e depois o deslocamento: ângulo uniforme e distância × √u, para cobrir o disco por igual. A ordem fica fixa no código e coberta por teste com valores esperados.
- **Impressão digital dos setores.** sha256 de `(id, grau, mancha, ocorrências próximas)` ordenado por id. Ela compara uma execução antiga com os dados atuais (FR-110).

## Modelo de dados (migration `0005_simulation`)
| Tabela | Campos principais |
|---|---|
| `simulation_runs` | `id` (uuid) · `created_at` · `mode` (`SIMULATION`/`HYBRID`) · `kind` = `SIMULATED` · `scenario` (jsonb) · `seed` · `members` · `simulation_engine_version` · `risk_engine_version` · `sectors_fingerprint` · `forecast_issued_at` (HYBRID) · `counts` (jsonb) · `comparison` (jsonb) · `duration_ms` |
| `simulation_results` | `run_id` (FK, cascade) · `sector_id` · `category` · `p_high` · `p_critical` · `p1h_max` · `p24` · `a72` · `rain_level` · `susceptibility` · `factors` (jsonb) — PK `(run_id, sector_id)` |

A simulação não entra em `data_sources`: ela não é uma fonte de dados, e uma linha ali apareceria na contagem de fontes e nos insights da Visão geral (BR-101).

## Backend
| Arquivo | Conteúdo |
|---|---|
| `app/simulation/scenario.py` | `Scenario`, `Area`, `Pattern` (dataclasses congeladas), validação de faixas (BR-104), presets (FR-103) |
| `app/simulation/rain.py` | hietograma → `p1h_max`/`p24`; fator espacial; chuva por setor; ajuste HYBRID sobre `RainInput` real |
| `app/simulation/ensemble.py` | variações com seed; agregação (moda, P(≥ alto), P(crítico), faixa 10–90%) |
| `app/simulation/engine.py` | `simulate(sectors, scenario, seed, members, base_rain=None)` → `SimulationResult`; `SIMULATION_ENGINE_VERSION = "0.1.0-experimental"` |
| `app/services/simulation.py` | leitura dos setores e pontos internos, execução, gravação, comparação com o último `risk_run`, retenção |
| `app/api/v1/simulation.py` | rotas do FR-104, FR-105 e FR-110; camada `/map/layers/simulation/{id}` em `maps.py` |
| `app/workers/tasks/simulation.py` | limpeza diária (NFR-102) |
| `pyproject.toml` | contrato do import-linter: `app.simulation` só importa `app.risk` |

## Frontend
- `features/simulation/{types,api,hooks,scenario}.ts`: o estado do formulário fica na URL, para dar link e voltar.
- `components/simulation/`:
  - `SimulationBanner` (BR-100), presente em todas as telas de resultado;
  - `ScenarioForm`, `PresetPicker`, `CenterPicker` (mapa, subprefeitura ou local salvo);
  - `ResultSummary`, `ComparisonTable`, `SectorRanking`, `SectorExplanation`;
  - `EnsembleControls` e `HistoryList` (Parte B).
- `app/simulation/page.tsx`: reaproveita `MapView` com uma camada própria (cor de simulação e hachura) e a legenda "Simulação".
- O registro de navegação marca `/simulation` como implementado.

## Testes
- Unitários (motor puro):
  - hietogramas;
  - fator espacial nas bordas (R e 2R);
  - AC-100 com setores sintéticos;
  - determinismo (AC-101 e AC-104) com valores de referência fixos para seed 42;
  - limites (AC-106);
  - HYBRID sem previsão → desconhecido (BR-103).
- Integração:
  - execução gravada e consultada;
  - isolamento (AC-103): contagens de `risk_runs` e respostas de `/risk/summary` e `/analytics/kpis` iguais antes e depois;
  - HYBRID com previsão vencida → 409 (AC-105);
  - retenção.
- Frontend:
  - faixa presente e anunciada (AC-107, axe);
  - preset preenche o formulário (AC-102);
  - parâmetros na URL.

## Ordem
1. Parte A: motor puro → migration → serviço e API → página → validação no navegador.
2. Parte B: variações → HYBRID → histórico → validação.
