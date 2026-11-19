# ADR-006 — PostGIS e sistemas de referência

**Status:** Aceita · **Data:** 2026-11-19

## Decisão
- Armazenar geometrias em **SRID 4326 (WGS84)**, tipo `geography` para pontos de estação (distâncias em metros corretas) e `geometry` para polígonos de análise.
- Para operações métricas em polígonos (buffer, área), transformar para **EPSG:31983 (SIRGAS 2000 / UTM 23S)**, que cobre São Paulo.
- Índices GiST em todas as colunas espaciais consultadas.

## Justificativa
WGS84 é o padrão de intercâmbio (GeoJSON, Leaflet, APIs). UTM 23S evita distorção em cálculos de área/buffer na região piloto.

## Consequências
Se a região expandir para fora da zona 23S, o SRID métrico passa a ser configurável por região.
