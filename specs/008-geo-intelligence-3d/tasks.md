# Tasks 008 — Geointeligência 3D

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — relevo e hidrografia

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T120 | Download e recorte do Copernicus DEM; texto de atribuição conferido | `integrations/copernicus/`, `ingestion/geo_jobs.py` | FR-120, AC-120, BR-123 | unitários + integração | [ ] |
| T121 | Hidrografia do GeoSampa (bacias, drenagem, piscinões) com respostas reais gravadas | `integrations/geosampa/hydro.py` | FR-121 | unitários + integração | [ ] |
| T122 | Migration `0007_geo` | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [ ] |
| T123 | Módulo puro de terreno (declividade, zonas, elevação relativa, perfil) | `geo/terrain.py`, `geo/raster.py` | NFR-120 | unitários | [ ] |
| T124 | Terreno por setor e métricas por bacia | `services/geo.py` | FR-122, AC-121, AC-123 | integração | [ ] |
| T125 | API: bacias, perfil, elevação de um ponto e camadas do mapa | `api/v1/geo.py`, `api/v1/maps.py` | FR-123 a FR-125, NFR-121, NFR-123, AC-122 | integração | [ ] |
| T126 | Página `/geo-3d`: mapa, ranking, ficha e perfil | `app/geo-3d/`, `components/geo/` | FR-126, NFR-124, AC-126 | `geo.test.tsx` | [ ] |
| T127 | Seção Terreno na explicação do setor | `components/geo/TerrainSection.tsx` | FR-127, BR-121 | idem | [ ] |
| T128 | Validação da Parte A no navegador e documentação | docs | Navegador + CI | manual | [ ] |

## Parte B — bloco 3D da bacia

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T129 | Grade reamostrada da bacia | `geo/raster.py`, `api/v1/geo.py` | FR-128, NFR-121 | unitários + integração | [ ] |
| T130 | Bloco 3D com Three.js e exagero vertical | `components/geo/BasinBlock3D.tsx` | FR-128, NFR-122 | `geo.test.tsx` (montagem da malha) | [ ] |
| T131 | Camadas sobre o bloco, incluindo simulação | idem | FR-129, AC-124 | idem | [ ] |
| T132 | Controles por teclado e exportação PNG | idem | FR-130 | idem | [ ] |
| T133 | Alternativa em 2D | `components/geo/BasinBlock2D.tsx` | FR-131, AC-125 | idem | [ ] |
| T134 | Validação da Parte B e documentação | docs | Navegador + CI | manual | [ ] |
