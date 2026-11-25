# ADR-018 — Retroteste do motor de risco com previsão arquivada e ocorrências do GeoSampa

- Status: **Aceita** (2026-11-25)
- Fase: 15 · Spec: [015](../../../specs/015-risk-evaluation/spec.md)

## Contexto
O motor v0 nunca foi conferido com alagamentos reais. A reanálise ERA5 (usada nas Análises) não
serve de entrada: em 2026-11-20 ela registrou 2–9 mm em dias com 49 e 54 ocorrências (ADR-012).
O motor ao vivo usa previsão de curto prazo, e o Open-Meteo guarda essas previsões (Historical
Forecast API, desde 2022).

## Decisão
Avaliar o motor por retroteste: para cada dia de 2026, rodar o motor puro (`app.risk`) com a chuva
prevista arquivada e comparar com as ocorrências do GeoSampa, por subprefeitura e dia. O fator de
ocorrências próximas de cada dia só conta ocorrências até a véspera. A calibração testa faixas de
chuva multiplicadas por fatores e só **recomenda**; o motor oficial não muda sem nova versão.

## Alternativas consideradas
- **Avaliar a operação ao vivo:** histórico de estimativas começa depois das últimas ocorrências publicadas.
- **Reanálise como entrada:** subestima chuva convectiva (ADR-012).
- **Previsão de véspera (Previous Runs API):** mais fiel à operação, mas multiplica as requisições por dia de antecedência; fica como evolução.

## Consequências
- Primeira medida objetiva do motor, recalculada todo dia.
- Resultado tende a ser otimista (primeiras horas de cada rodada) e afetado pelo sub-registro de ocorrências; a interface diz isso.
