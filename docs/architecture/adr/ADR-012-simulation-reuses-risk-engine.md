# ADR-012 — Simulação reaproveita o motor de risco, na resolução de setor

**Status:** Proposta · **Data:** 2026-11-20

## Contexto
A Fase 7 pede cenários "e se?" com seed e os modos `SIMULATION` e `HYBRID`. O motor de risco v0 (ADR-010) é puro e determinístico. Ele recebe, por ponto de previsão, a chuva máxima em 1 h, o total em 24 h e o acumulado de 72 h, e devolve a categoria de cada setor com a explicação.

Em 2026-11-20 testamos reproduzir dias reais de 2026 com a reanálise horária ERA5 (Open-Meteo). Ela registra 2–9 mm em dias com 49 e 54 ocorrências de alagamento. A reanálise não serve de entrada para reprodução de eventos.

## Opções
1. **Motor de simulação separado**, com regras próprias: risco de divergir do motor oficial e de mostrar resultados que o motor real nunca daria.
2. **Gerar chuva nos 12 pontos de previsão** e chamar o motor como está: uma célula de chuva de poucos km cairia entre os pontos e não atingiria ninguém.
3. **Gerar chuva por setor e chamar o motor de risco sem mudanças**: cada setor recebe a própria chave de ponto.
4. **Reproduzir eventos passados com a reanálise**: descartada pelo teste acima.

## Decisão
Opção 3. `app/simulation/` só gera chuva (hietograma, fator espacial, variações com seed, ajuste sobre a previsão real) e chama `app.risk.engine.assess`. Resultados ficam em tabelas próprias, com `kind = SIMULATED`, e não aparecem em nenhuma tela de dado real.

## Consequências
- Qualquer mudança no motor de risco vale também para a simulação. As duas versões ficam gravadas em cada execução.
- A simulação herda os limites do motor v0: faixas não calibradas, nenhuma hidrologia.
- Reprodução de eventos passados volta à pauta quando houver chuva horária medida: INMET, ou o importador do CEMADEN da spec 002b.
