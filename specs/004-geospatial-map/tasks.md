# Tasks 004 — Mapa geoespacial 2D/3D

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T040 | GeoJSON puro e polígono do bbox | `services/geojson.py` | AC-054 | `test_geojson.py` | [ ] |
| T041 | Camadas: estações e pontos de previsão com chuva 24 h | `services/map_layers.py` | FR-051, FR-052, BR-052 | integração | [ ] |
| T042 | Rotas `/map/*` | `api/v1/map.py` | FR-050 a FR-052 | `test_map_api.py` | [ ] |
| T043 | Estado ↔ URL, geometria e escalas | `features/map/*` | FR-059, BR-050, BR-051; AC-052 | `map.test.ts` | [ ] |
| T044 | MapView (MapLibre, 2D/3D, relevo, camadas, popups) | `components/map/MapView.tsx` | FR-053 a FR-055; AC-051 | navegador real | [ ] |
| T045 | Legenda, lista acessível, controles, reserva sem WebGL | `components/map/*`, `app/map/page.tsx` | FR-056 a FR-058; AC-050, AC-053 | `map-ui.test.tsx` | [ ] |
| T046 | Dependência maplibre-gl + lockfile; navegação | `package.json`, `registry.ts` | `npm ci` no CI | CI | [ ] |
| T047 | Validação no navegador e documentação | docs | 2D e 3D verificados com dados reais | manual | [ ] |
