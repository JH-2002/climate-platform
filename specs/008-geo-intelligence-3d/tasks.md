# Tasks 008 — Geointeligência 3D

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — relevo e hidrografia

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T120 | Download e recorte do Copernicus DEM; texto de atribuição conferido | `integrations/copernicus/`, `ingestion/geo_jobs.py` | FR-120, AC-120, BR-123 | unitários + integração | [x] |
| T121 | Hidrografia do GeoSampa (bacias, drenagem, piscinões) com respostas reais gravadas | `integrations/geosampa/hydro.py` | FR-121 | unitários + integração | [x] |
| T122 | Migration `0007_geo` | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [x] |
| T123 | Módulo puro de terreno (declividade, zonas, elevação relativa, perfil) | `geo/terrain.py`, `geo/raster.py` | NFR-120 | unitários | [x] |
| T124 | Terreno por setor e métricas por bacia | `services/geo.py` | FR-122, AC-121, AC-123 | integração | [x] |
| T125 | API: bacias, perfil, elevação de um ponto e camadas do mapa | `api/v1/geo.py`, `api/v1/maps.py` | FR-123 a FR-125, NFR-121, NFR-123, AC-122 | integração | [x] |
| T126 | Página `/geo-3d`: mapa, ranking, ficha e perfil | `app/geo-3d/`, `components/geo/` | FR-126, NFR-124, AC-126 | `geo.test.tsx` | [x] |
| T127 | Seção Terreno na explicação do setor | `components/geo/TerrainSection.tsx` | FR-127, BR-121 | idem | [x] |
| T128 | Validação da Parte A no navegador e documentação | docs | Navegador + CI | manual | [x] |

Validação da Parte A (2026-11-24), com os dados reais:
- **Hidrografia:** 269 bacias, 28.366 trechos de drenagem e 72 piscinões. Os 793 setores ficaram dentro de alguma bacia (AC-123).
- **Relevo:** recorte do Copernicus com ~28 m de resolução. 771 setores (97%) ficam abaixo do entorno de 1 km (mediana de 18 m abaixo) e metade toca um curso d'água: são setores de fundo de vale, como esperado (AC-121). A elevação das bacias vai de 715 m (várzeas) a 1.221 m (Cantareira). A Praça da Sé dá 756 m.
- **Perfil na Penha:** o ponto mais baixo (715 m) fica a 34 m de onde o Rio Tietê aparece no perfil (AC-122). Cada perfil leva de 18 a 133 ms.
- **Limitação:** 351 setores (44%) têm menos de 4 células e aparecem como "pouca amostra".
- **Correções da validação:**
  - a imagem do backend não tinha a `libexpat1`, que o rasterio usa;
  - os nomes dos córregos no topo do perfil eram cortados e se sobrepunham;
  - o exemplo "Pinheiros → Paulista" não cruzava o rio e agora parte do Butantã.

## Parte B — bloco 3D da bacia

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T129 | Blocos de relevo "terrarium" do Copernicus e ficha do bloco da bacia | `geo/terrain.py`, `geo/png.py`, `services/geo_relief.py`, `api/v1/geo.py` | FR-128, NFR-121 | unitários + integração | [ ] |
| T130 | Bloco 3D no MapLibre sobre o relevo do Copernicus, com exagero vertical | `components/geo/BasinBlock3D.tsx` | FR-128, NFR-122 | `geo.test.tsx` | [ ] |
| T131 | Camadas sobre o bloco, incluindo simulação | idem | FR-129, AC-124 | idem | [ ] |
| T132 | Controles por teclado e exportação PNG | idem | FR-130 | idem | [ ] |
| T133 | Alternativa em 2D (relevo sombreado em PNG e tabela) | `services/geo_relief.py`, `components/geo/BasinBlock2D.tsx` | FR-131, AC-125 | integração + `geo.test.tsx` | [ ] |
| T134 | Validação da Parte B e documentação | docs | Navegador + CI | manual | [ ] |
