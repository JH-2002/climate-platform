# ADR-013 — Terreno do Copernicus DEM em arquivo e hidrografia oficial do GeoSampa

**Status:** Aceita · **Data:** 2026-11-20

## Contexto
A Fase 8 precisa de terreno para métricas por setor, perfil e bloco 3D, e de bacias e drenagem para organizar o risco por bacia. Testado em 2026-11-20:
- **Copernicus DEM GLO-30:** público por HTTPS (2 blocos de 1°, ~47 MB). É um modelo de superfície de 30 m.
- **GeoSampa:** publica por WFS 269 bacias, 28.366 trechos de drenagem e 72 piscinões.
- **LiDAR da Prefeitura (2020):** existe, mas em nuvens de pontos por folha (5.401 folhas), baixadas uma a uma no portal.

## Opções
Terreno:
1. **Copernicus em GeoTIFF num volume, lido com rasterio.**
2. Copernicus no PostGIS raster: exige drivers do GDAL habilitados no banco e carga por linha de comando, e não traz ganho para consultas por janela.
3. LiDAR da Prefeitura: muito mais preciso, mas sem download automatizável para a cidade.
4. Terrain Tiles (o relevo visual da Fase 4): sem garantia de fonte e de versão para cálculo.

Bacias e drenagem:
- **A.** Camadas oficiais do GeoSampa.
- **B.** Derivar do DEM (direção de fluxo e acumulação): os prédios do modelo de superfície desviam o escoamento, e o resultado divergiria da rede real, que é canalizada e subterrânea em boa parte.

## Decisão
Opção 1 com A.

## Consequências
- Nova dependência de sistema no backend (`rasterio`, que traz o GDAL na wheel) e um volume `dem-data`.
- As métricas de terreno são comparativas (bairro e bacia), com aviso de modelo de superfície. Elas não alteram o risco nesta fase.
- O LiDAR fica como melhoria para o detalhe local, com download manual por folha.
- A mancha de inundação continua sendo só a oficial: nenhuma área inundável é derivada do relevo.

## Revisão (2026-11-24) — bloco 3D sem Three.js
O bloco 3D da bacia usa o terreno 3D do MapLibre (ADR-009), alimentado por blocos de relevo "terrarium" que o backend gera do recorte do Copernicus.
- **3D e cálculos sobre o mesmo dado:** o relevo visual deixa de vir dos Terrain Tiles nessa vista.
- **Nenhuma dependência nova no frontend:** órbita, toque e teclado vêm prontos.
- **Alternativa em 2D:** relevo sombreado em PNG gerado no servidor.

O Three.js continua permitido pela Constituição para análises 3D que o MapLibre não cubra.
