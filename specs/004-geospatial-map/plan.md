# Plan 004 — Mapa geoespacial 2D/3D

## Decisão
**ADR-009:** MapLibre GL JS em vez de Leaflet — um único mapa WebGL que faz 2D e 3D (relevo, inclinação, extrusões), com reserva automática em lista quando não há WebGL. Leaflet não faz 3D; Three.js puro exigiria reimplementar mapa base e navegação.

## Backend
| Arquivo | Responsabilidade |
|---|---|
| `app/services/geojson.py` | Construtores puros de Feature/FeatureCollection e polígono do bbox |
| `app/services/map_layers.py` | Consultas das camadas (estações, pontos de previsão com chuva 24 h) |
| `app/api/v1/map.py` | `/map/region`, `/map/layers/stations`, `/map/layers/forecast-points` |
| `app/api/v1/deps.py` | `get_clock` compartilhado (movido de `weather.py`) |

## Frontend
| Arquivo | Responsabilidade |
|---|---|
| `features/map/state.ts` | Modo e camadas ↔ URL (puro) |
| `features/map/geometry.ts` | Polígono circular para colunas 3D; faixas e escala de chuva (puro) |
| `features/map/api.ts`, `hooks.ts` | Busca das camadas |
| `components/map/MapView.tsx` | MapLibre (import dinâmico), fontes, camadas, terreno, popups |
| `components/map/MapLegend.tsx`, `MapFeatureList.tsx`, `MapControls.tsx` | Legenda, lista acessível, controles |
| `app/map/page.tsx` | Composição, detecção de WebGL e de movimento reduzido |

Camadas MapLibre: `regiao` (linha), `estacoes` (círculo, cor por situação), `chuva-2d` (círculo, raio pela chuva), `chuva-3d` (fill-extrusion, altura pela chuva), `locais` (círculo). Relevo: fonte `raster-dem` com `encoding: terrarium`, `setTerrain({exaggeration: 1.5})` em 3D, sombreamento (`hillshade`) nos dois modos.

## Testes
- Unitários backend: GeoJSON e bbox; integração: as três rotas com dados das respostas reais gravadas.
- Frontend: estado ↔ URL, polígono e escala, legenda, lista, aviso sem WebGL. O canvas WebGL não roda no jsdom; ele é verificado no navegador real (T047).

## Ordem
T040 → T041 → T042 → T043 → T044 → T045 → T046 → T047.
