# ADR-007 — "Agora" a partir da previsão horária, rotulado como estimativa

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
As observações medidas do INMET dependem de token. O painel precisa mostrar algo útil para "agora" sem violar a regra de nunca apresentar estimativa como medição (Constituição §7, ADR-003).

## Opções
1. Deixar "Agora" vazio até o token chegar.
2. Usar o endpoint de "condições atuais" da Open-Meteo como se fosse medição. **Rejeitada** (viola ADR-003).
3. **Mostrar a previsão horária da hora corrente, rotulada como estimativa de modelo, com fonte e horário da coleta.**

## Decisão
Opção 3. A seção de medições continua existindo e exibe "indisponível" com o motivo.

## Consequências
Quando o token chegar, o painel mostra medição e estimativa lado a lado; a estimativa não substitui a medição.
