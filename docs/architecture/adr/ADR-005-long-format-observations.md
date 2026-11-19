# ADR-005 — Observações em formato longo

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
Fontes diferentes publicam conjuntos diferentes de variáveis, com frequências diferentes (INMET horário, CEMADEN 10 min só chuva, ANA nível/vazão).

## Opções
1. **Formato largo** — uma coluna por variável. Consultas simples; muitas colunas nulas, migração a cada nova variável.
2. **Formato longo** — `(station_id, variable, observed_at, value, unit, quality_flag)`. Uniforme entre fontes, qualidade por valor; consultas multivariável exigem pivot.

## Decisão
Formato longo em `weather_observations`, com `variable` restrita a um catálogo (enum/tabela `variables` com unidade canônica). Agregados (`precipitation_aggregates`) e visões materializadas em formato largo quando a Fase 3 medir necessidade.

## Consequências
- `quality_flag` e proveniência por valor, alinhado à Constituição §7.
- Volume estimado: ~50 estações × 10 variáveis × 24 h ≈ 12 mil linhas/dia → ~4,4 M/ano. Particionamento por mês avaliado quando passar de ~50 M linhas.
