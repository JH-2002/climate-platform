# ADR-011 — Séries de referência para análises e insights por regra

**Status:** Proposta · **Data:** 2026-11-19

## Contexto
A Fase 6 pede percentis históricos, anomalias, sazonalidade, tendências e insights automáticos (documento mestre §13). Em 2026-11-19 o sistema não tinha nenhuma série longa:
- previsão de 7 dias;
- ocorrências de 2026;
- observações do INMET bloqueadas pelo token.

Sem série longa, "acima do normal" seria inventado.

## Opções
1. Adiar a Fase 6 até o token do INMET e acumular anos de dados próprios.
2. Usar só a previsão acumulada: período curto demais (Constituição §13).
3. **Duas séries de referência complementares:**
   - chuva mensal **medida** do IAG/USP (1933–2025, publicada pela Prefeitura): clima e normais;
   - reanálise diária ERA5/ERA5-Land da Open-Meteo (1991 até ontem): percentis diários e anomalias no mesmo ponto da grade usada pela previsão.

Sobre os insights:
- **A.** Regras documentadas com frases-modelo preenchidas por métricas.
- **B.** Texto gerado por modelo de linguagem a partir das métricas.

## Decisão
Opção 3 com insights do tipo A.

## Consequências
- Comparações de previsão e de mês corrente são feitas contra a reanálise do mesmo ponto, que tem o mesmo viés. Isso evita comparar modelo com medição.
- Afirmações climáticas usam só a série medida de 93 anos, e mesmo assim sem atribuir causa.
- A reanálise tem chuva em células de ~25 km e subestima temporais. Isso é dito em cada gráfico, e ela não é usada para valores absolutos de chuva extrema.
- Cada insight é reproduzível a partir das métricas que ele mesmo lista. Um texto por IA poderá ser adicionado no futuro só como reescrita dessas métricas, nunca como fonte de causas ou números (documento mestre §13.9).
- A tabela do IAG não tem API: atualização anual assistida por script, com conferência das somas.
