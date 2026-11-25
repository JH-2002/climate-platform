# ADR-009 — MapLibre GL para o mapa 2D/3D

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
O plano original previa Leaflet (2D) na Fase 4 e Three.js (3D) na Fase 8. O responsável pediu um mapa 3D já na Fase 4. O documento mestre exige reserva 2D para o 3D (14.5) e desaconselha 3D complexo antes de um 2D funcional (26.7).

## Opções
1. Leaflet 2D agora, 3D só na Fase 8 (plano original).
2. Só 3D (Three.js/deck.gl), sem versão plana — contraria 14.5.
3. **MapLibre GL JS**: mapa WebGL com mapa base vetorial, relevo (`raster-dem`), inclinação e extrusões; o mesmo mapa fica plano em 2D.

## Decisão
Opção 3, com mapa base OpenFreeMap (sem chave, atribuição automática) e relevo AWS Terrain Tiles (Terrarium), ambos testados a partir da rede do responsável. URLs configuráveis.

## Consequências
- Um componente atende 2D e 3D; sem WebGL, a página mostra a lista (reserva).
- A Fase 8 continua existindo para análise 3D (Three.js, Copernicus DEM, bacias, simulações), agora apoiada no mapa MapLibre.
- `react-leaflet` sai da stack prevista; a constituição (§3) é atualizada.
