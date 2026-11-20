# ADR-010 — GeoSampa como base de suscetibilidade e motor de risco em matriz

**Status:** Proposta · **Data:** 2026-11-19

## Contexto
O roteiro previa ANA e CGE como dependências da Fase 5. A ANA exige cadastro e mede níveis de rio, não alagamento urbano. O CGE não tem API pública. Sem dados de suscetibilidade, um "risco de alagamento" seria só chuva prevista com outro nome.

Em 2026-11-19 o WFS aberto do GeoSampa respondeu, a partir da rede do responsável, com:
- setores de risco hidrológico vistoriados (R1–R4, 793 polígonos);
- manchas de inundação de 100 anos;
- ocorrências de alagamento e inundação do ano corrente.

## Opções
1. Esperar cadastro na ANA e acesso ao CGE.
2. Índice contínuo ponderado (ex.: 0,5·chuva + 0,3·relevo + 0,2·histórico), com pesos arbitrários.
3. **Matriz de regras** (nível de chuva 0–3 × suscetibilidade 1–4 → baixo/moderado/alto/crítico), com suscetibilidade tirada dos setores oficiais e ajustada por manchas e ocorrências.

## Decisão
Opção 3, com GeoSampa como fonte (sincronização diária) e Open-Meteo como gatilho de chuva, até que haja observações do INMET.

## Consequências
- Cada resultado se explica em uma frase ("chuva forte prevista + setor R3") e é reproduzível pela versão do motor.
- Não há números de precisão falsa: a saída é uma categoria, não uma probabilidade.
- Fora dos setores mapeados o sistema não estima risco; ele diz isso.
- A calibração das faixas fica para quando houver séries de ocorrências de vários anos (Fase 6/7). A versão do motor muda a cada ajuste de coeficiente.
- ANA e CGE continuam no roteiro como melhorias, não como bloqueios.
