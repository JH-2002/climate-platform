# Spec 015 — Avaliação retrospectiva do motor de risco

> Status: **Em andamento** (2026-11-25) · Fase: 15 · ADR: [ADR-018](../../docs/architecture/adr/ADR-018-risk-hindcast.md)

## Contexto
O motor de risco v0 (spec 005) é experimental: as faixas de chuva (10/25/50 mm em 1 h, 30/60/100 mm
em 24 h) vieram da classificação usual de intensidade, nunca foram conferidas com alagamentos
reais de São Paulo. A melhoria "calibrar as faixas com ocorrências passadas" está pendente desde
a Fase 5. O histórico de estimativas da plataforma começa em 2026-11-19, depois das últimas
ocorrências publicadas pelo GeoSampa (até 2026-10-28), então ainda não dá para avaliar a operação
ao vivo.

## Objetivo
Medir, com dados de 2026, quanto o motor acerta: rodá-lo para cada dia passado com a chuva
**prevista** arquivada (a mesma fonte que ele usa ao vivo) e comparar com as ocorrências de
alagamento registradas pela Prefeitura. Mostrar o resultado em linguagem simples e testar faixas
de chuva alternativas, sem mudar o motor oficial.

## Escopo
- Arquivo de previsões horárias de chuva (Open-Meteo Historical Forecast API) dos 12 pontos, desde 2026-01-01, com atualização diária.
- Retroteste diário do motor, sem vazamento: o fator "ocorrências próximas" de cada dia só conta ocorrências até a véspera.
- Métricas por subprefeitura e dia, confiabilidade por categoria, calibração das faixas de chuva e resultado por mês.
- Aba "Avaliação do risco" em Análises, com tabelas acessíveis.

**Fora do escopo:** trocar os coeficientes do motor (a calibração só recomenda; mudar exige nova
`ENGINE_VERSION` e decisão registrada); avaliar a operação ao vivo (quando houver ocorrências
publicadas depois de 2026-11-19, a mesma rotina passa a cobri-la).

## Requisitos funcionais
- **FR-210 Arquivo de previsões.** Fonte `open-meteo-historical-forecast` (CC BY 4.0, `kind = FORECAST`): precipitação horária de cada ponto da grade, de 2026-01-01 até ontem, em UTC. Uma requisição por ponto e por execução; as execuções seguintes buscam só do último dia guardado menos 3 (a fonte revisa os dias recentes) até ontem.
- **FR-211 Unidade de avaliação.** Subprefeitura × dia local. Previsão positiva: algum setor da subprefeitura com categoria **alto** ou **crítico**. Observação positiva: ao menos uma ocorrência registrada na subprefeitura naquele dia. Dias-subprefeitura em que todos os setores ficaram "desconhecido" saem da conta.
- **FR-212 Retroteste.** Para cada dia D com 72 h de chuva antecedente disponível: janela de 24 h a partir de 00:00 local, setores ativos de hoje, ocorrências próximas contadas na janela de 365 dias que termina em D−1, mesmo ponto de previsão mais próximo do motor ao vivo.
- **FR-213 Métricas.** Tabela de contingência (acertos, falhas, alarmes falsos, negativos corretos), taxa de detecção (POD), razão de alarmes falsos (FAR), índice de sucesso crítico (CSI), viés de frequência e taxa básica. Confiabilidade: para cada categoria máxima do dia-subprefeitura, quantos tiveram ocorrência. Resultado por mês.
- **FR-214 Calibração.** As mesmas métricas com as faixas de chuva (1 h e 24 h) multiplicadas por fatores de 0,5 a 1,5 (passo 0,1). Mostra o fator atual (1,0), o de maior CSI e quanto ele mudaria POD e FAR. É recomendação, não muda o motor.
- **FR-215 Rotina.** Arquivo atualizado e avaliação recalculada uma vez por dia; resultado guardado (as 10 últimas avaliações). `GET /api/v1/analytics/risk-evaluation` devolve a mais recente.
- **FR-216 Interface.** Aba "Avaliação do risco" em Análises: resumo em frases ("de cada 10 dias-subprefeitura com alagamento registrado, o sistema marcou N como alto ou crítico"), tabela de contingência, confiabilidade (gráfico e tabela), calibração (gráfico e tabela), resultado por mês e limitações. Relatório disponível pelo atalho existente das Análises.

## Regras de negócio
- **BR-210** A avaliação usa previsão arquivada e ocorrências registradas; nunca é apresentada como precisão garantida do sistema. As limitações aparecem junto dos números.
- **BR-211** Ocorrências registradas são um subconjunto dos alagamentos reais (sub-registro): "alarme falso" pode ser alagamento não registrado; o texto diz isso.

## Critérios de aceite
- **AC-210** Com um conjunto pequeno de dias, setores e ocorrências, as métricas batem com o cálculo à mão (teste unitário).
- **AC-211** O fator de ocorrências próximas de um dia D não inclui ocorrências de D (teste).
- **AC-212** A aba mostra métricas, confiabilidade, calibração e o mês a mês, com axe sem violações graves.
- **AC-213** Na vitrine, a aba aparece com os dados calculados no Actions.

## Riscos e limitações
- A previsão arquivada junta as primeiras horas de cada rodada do modelo: é melhor que a previsão de véspera que o motor usa ao vivo, então o retroteste tende a ser otimista.
- A malha de 12 pontos não vê chuvas muito localizadas.
- As ocorrências do GeoSampa podem ser revisadas e publicadas com atraso.
