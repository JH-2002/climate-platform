# ADR-002 — Região piloto: Município de São Paulo

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
O documento mestre não define a área geográfica. Ingerir o Brasil inteiro desde o início multiplica volume, custo de validação e esforço de qualidade de dados, e dilui a análise de risco, que depende de dados locais (drenagem, ocorrências, hidrografia).

## Opções consideradas
1. Brasil inteiro desde a Fase 2.
2. Um estado (SP).
3. **Município de São Paulo como piloto, expandindo para a RMSP.**

## Decisão
Opção 3. A região é configurável (`REGION_BBOX`, lista de estações), não fixa no código.

## Justificativa
- Problema real e recorrente de alagamentos, com órgão municipal ativo (CGE) e dados geográficos ricos (GeoSampa).
- Estações INMET disponíveis na capital e entorno; densa rede de pluviômetros CEMADEN/CGE.
- O responsável pelo projeto está em São Paulo, o que facilita validação qualitativa.

## Consequências
- Lista inicial de estações INMET da capital/RMSP será definida na T014 a partir de `/estacoes/T` (filtrar por `SG_ESTADO = SP` e bbox).
- Expansão para outras regiões exige apenas configuração + validação de cobertura.
