# Tasks 004 — Mapa geoespacial 2D/3D

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T040 | GeoJSON puro e polígono do bbox | `services/geojson.py` | AC-054 | `test_geojson.py` | [x] |
| T041 | Camadas: estações e pontos de previsão com chuva 24 h | `services/map_layers.py` | FR-051, FR-052, BR-052 | integração | [x] |
| T042 | Rotas `/map/*` | `api/v1/map.py` | FR-050 a FR-052 | `test_map_api.py` | [x] |
| T043 | Estado ↔ URL, geometria e escalas | `features/map/*` | FR-059, BR-050, BR-051; AC-052 | `map.test.ts` | [x] |
| T044 | MapView (MapLibre, 2D/3D, relevo, camadas, popups) | `components/map/MapView.tsx` | FR-053 a FR-055; AC-051 | navegador real | [x] |
| T045 | Legenda, lista acessível, controles, reserva sem WebGL | `components/map/*`, `app/map/page.tsx` | FR-056 a FR-058; AC-050, AC-053 | `map-ui.test.tsx` | [x] |
| T046 | Dependência maplibre-gl + lockfile; navegação | `package.json`, `registry.ts` | `npm ci` no CI | CI | [x] |
| T047 | Validação no navegador e documentação | docs | 2D e 3D verificados com dados reais | manual | [x] |

## Validação (2026-11-19)

- CI verde no commit `6f5c5c1`.
- No navegador (Docker local): mapa 3D com relevo e colunas de chuva, alternância para 2D, retângulo da região de interesse, popup da estação A701 ("Medições: aguardando token do INMET"), legenda e lista acessível com A701, A771 e o ponto de previsão (4,6 mm em 24 h).
- Problema encontrado e corrigido: o worker do MapLibre 6 não carregava no Next (servido como `text/html`). Solução: copiar `maplibre-gl-worker.mjs` para `public/vendor/` nos scripts `predev`/`prebuild` e usar `setWorkerUrl`.
