# Plan 008 — Geointeligência 3D

## Decisões
- **DEM em arquivo, não no banco** ([ADR-013](../../docs/architecture/adr/ADR-013-terrain-and-hydrography.md)). O recorte da região (cerca de 2.400 × 2.300 células, float32, ~20 MB comprimido) fica num GeoTIFF num volume Docker (`dem-data`). O PostGIS raster exigiria drivers do GDAL habilitados no banco e carga por linha de comando. Com o arquivo, o rasterio lê só a janela que precisa.
- **Leitura isolada.** `app/integrations/copernicus/` baixa os blocos e grava o recorte. `app/geo/raster.py` abre o arquivo e entrega matrizes numpy. `app/geo/terrain.py` é puro, com declividade, estatísticas de zona, elevação relativa e amostragem de perfil sobre matrizes, e é testado sem arquivo.
- **Projeção.** Os cálculos métricos (declividade, distâncias, entorno de 1 km) usam SIRGAS 2000 / UTM 23S (EPSG:31983, Constituição §8). O GeoSampa já entrega as camadas nessa projeção, e o banco guarda em 4326 como as demais.
- **Drenagem no mapa.** Recorte por área visível com `ST_Intersects` e simplificação por zoom (`ST_SimplifyPreserveTopology`, com tolerância conforme o zoom). Abaixo do zoom 12, só os trechos abertos e canalizados a céu aberto.
- **Bloco 3D.** O backend reamostra a grade da bacia, por média, para no máximo 256 × 256 e devolve `Float32Array` em base64 com os metadados. O frontend usa `three` puro, sem R3F, para manter o pacote pequeno, em um componente carregado com `dynamic(..., { ssr: false })`.

## Modelo de dados (migration `0007_geo`)
| Tabela | Campos principais |
|---|---|
| `basins` | `id` · `source_id` · `source_code` · `name` · `main_basin` · `area_km2` · `geom` (MultiPolygon 4326) · `active` · `last_seen_at` · `raw_payload_id` |
| `drainage_segments` | `id` · `source_id` · `source_code` · `name` · `course_type` (aberto/canalizado/subterrâneo…) · `length_m` · `geom` (MultiLineString) · `active` · … |
| `detention_reservoirs` | `id` · `source_id` · `source_code` · `name` · `basin_name` · `main_basin` · `volume_m3` · `kind` · `subprefecture` · `geom` · … |
| `sector_terrain` | `sector_id` (PK) · `computed_at` · `dem_version` · `elev_median_m` · `elev_min_m` · `slope_mean_pct` · `relative_elev_m` · `cells` · `low_sample` · `basin_id` · `nearest_drainage_id` · `nearest_drainage_m` |
| `dem_assets` | `id` · `source_id` · `tile_code` · `etag` · `bytes` · `downloaded_at` · `clip_path` · `clip_sha256` · `resolution_m` |

Mais 4 fontes em `data_sources`: `copernicus-dem`, `geosampa-basins`, `geosampa-drainage` e `geosampa-reservoirs`.

## Backend
| Arquivo | Conteúdo |
|---|---|
| `integrations/copernicus/dem.py` | URLs dos blocos, download em streaming com conferência de ETag e tamanho, recorte (rasterio) |
| `integrations/geosampa/hydro.py` | Parse das 3 camadas, normalização do tipo de trecho |
| `geo/terrain.py` | Puro: declividade (Horn), estatística de zona por máscara, elevação relativa, amostragem bilinear do perfil |
| `geo/raster.py` | Abre o recorte (cache por processo), máscara de polígono, janela da bacia, reamostragem |
| `services/geo.py` | Métricas de setor e bacia, perfil, elevação de um ponto, grade da bacia |
| `ingestion/geo_jobs.py` + `runner.py` | DEM (uma vez), hidrografia (30 dias), recálculo do terreno |
| `api/v1/geo.py` + `maps.py` | Rotas do FR-123 ao FR-125 e do FR-128 |
| `pyproject.toml` | `rasterio`, `numpy`; contrato do import-linter: `app.geo.terrain` é puro |

## Frontend
- `features/geo/{types,api,hooks,state}.ts`.
- `components/geo/`:
  - `BasinRanking`, `BasinCard`, `ProfileChart` (Recharts, com tabela) e `TerrainSection` (usada pela Risco e pelo Laboratório);
  - `BasinBlock3D` (three, carregamento dinâmico) e `BasinBlock2D` (alternativa);
  - `TerrainDisclaimer` (BR-120).
- `app/geo-3d/page.tsx`: o mapa (reaproveita `MapView` com camadas novas) e as abas Bacias, Perfil e Bloco 3D. O registro de navegação marca `/geo-3d` como implementado.

## Testes
- Unitários:
  - declividade e estatísticas em grades sintéticas com resposta conhecida (plano inclinado, vale em V);
  - elevação relativa;
  - perfil (distâncias, interpolação, cruzamentos);
  - parse das camadas do GeoSampa com respostas reais gravadas (recortes pequenos).
- Integração:
  - recorte real do DEM como fixture, de no máximo 200 KB, com uma janela perto do Tietê;
  - AC-121 a AC-123 com setores e drenagem gravados;
  - limites do perfil (20 km, 10 pontos).
- Frontend:
  - ranking, ficha e perfil (tabela e axe);
  - alternativa em 2D (AC-125);
  - seção Terreno na explicação do setor.

## Ordem
1. Parte A: DEM e hidrografia → métricas → API → página com mapa, ranking e perfil → seção Terreno → validação.
2. Parte B: grade da bacia → bloco 3D → simulação sobre o bloco → alternativa em 2D → validação.
