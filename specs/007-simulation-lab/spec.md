# Spec 007 — Laboratório de simulação (Simulation Lab)

> Status: **Em revisão** (2026-11-20) · Fase: 7 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md) · ADR: [ADR-012](../../docs/architecture/adr/ADR-012-simulation-reuses-risk-engine.md)

## Contexto
O documento mestre prevê um laboratório de cenários com seed e os modos `SIMULATION` e `HYBRID` (Constituição §7). A pergunta que ele responde é **"e se?"**: o que o motor de risco estimaria se chovesse X mm em Y horas sobre tal região, com o solo assim ou assado.

**O que já existe:**
- o motor de risco v0 é **puro e determinístico** (`app/risk/engine.py`). Ele recebe setores e, para cada ponto, a chuva máxima em 1 h, o total em 24 h e o acumulado das 72 h anteriores;
- 793 setores de risco hidrológico do GeoSampa, com grau R1–R4, mancha de inundação e ocorrências próximas;
- a previsão real de 12 pontos, com as 72 h anteriores;
- 630 ocorrências de 2026, em 100 dias diferentes.

**Testado em 2026-11-20: reproduzir dias reais com a reanálise não funciona.** A reanálise horária da Open-Meteo (ERA5) suaviza demais as tempestades de verão:

| Dia | Ocorrências registradas | Chuva na reanálise (4 pontos da cidade) |
|---|---|---|
| 28/01/2026 | 54 | 4–9 mm no dia, máximo de 2,5–5,5 mm em 1 h |
| 06/03/2026 | 49 | 2–6 mm no dia, máximo de 1,8–5,2 mm em 1 h |
| 14/09/2026 | 33 | 24–27 mm no dia; 68–79 mm nas 72 h anteriores |

Com esses números, o motor classificaria quase tudo como "baixo" em dias com dezenas de alagamentos. A falha estaria na entrada, não no motor, mas a tela não teria como deixar isso claro. **Reproduzir eventos passados fica fora desta fase** e espera chuva horária medida: INMET, ou o importador do CEMADEN da spec 002b.

## Objetivo
Permitir montar um cenário de chuva, ver o que o motor de risco estimaria para cada setor e comparar com a estimativa real de agora, sem nenhuma chance de confundir simulação com previsão ou alerta.

## Escopo
Dividido em duas partes, entregues e validadas em sequência.

**Parte A — cenários determinísticos (`SIMULATION`)**
- Motor de simulação puro (`app/simulation/`) que transforma um cenário em chuva por setor e chama o motor de risco existente.
- Cenário:
  - chuva total;
  - duração;
  - distribuição no tempo;
  - área atingida: cidade inteira ou célula de chuva com centro e raio;
  - chuva das 72 h anteriores.
- Cenários prontos (presets) com origem documentada.
- Gravação das execuções em tabelas próprias, com link para abrir de novo.
- Página `/simulation` com formulário, mapa dos setores simulados, contagem por categoria, ranking, explicação por setor e comparação com a estimativa real mais recente.

**Parte B — incerteza com seed e modo `HYBRID`**
- Conjunto de N variações (até 100) com seed. Cada variação muda a intensidade e a posição da célula de chuva. O resultado por setor é a categoria mais frequente e a probabilidade de chegar a alto ou crítico.
- Modo `HYBRID`: parte da previsão real das próximas 24 h e das 72 h anteriores reais, com um ajuste do usuário: multiplicar a previsão ou somar uma célula de chuva.
- Histórico das simulações recentes e reexecução com o mesmo seed.

**Fora do escopo**
- Reproduzir eventos passados (ver Contexto).
- Mudar coeficientes do motor de risco pela interface: a simulação usa o motor oficial, na versão em uso.
- Hidrologia (escoamento, rede de drenagem, nível de rio): o motor v0 é uma matriz de chuva × suscetibilidade, e a simulação herda isso.
- Alertas de simulação (Fase 9).
- Login: as simulações são públicas como o resto da plataforma, sem dado pessoal.

## User stories
- **US-070** Como gestor, quero ver quais setores ficariam em risco alto ou crítico se caísse uma tempestade forte sobre uma região, para planejar ações.
- **US-071** Como analista, quero comparar o cenário com a estimativa real de agora e ver o que mudaria.
- **US-072** Como pesquisador, quero repetir uma simulação e obter exatamente o mesmo resultado (seed e versões registradas).
- **US-073** Como morador, quero entender, sem chance de engano, que estou olhando uma simulação e não uma previsão.
- **US-074** Como analista, quero partir da previsão real e perguntar "e se chover o dobro?".

## Requisitos funcionais
### Parte A
- **FR-100 Cenário.** Um cenário tem:
  - total de chuva, de 1 a 300 mm;
  - duração, de 1 a 24 h;
  - padrão no tempo: constante, concentrado (50% do total na hora de pico) ou muito concentrado (70% na hora de pico);
  - área: cidade inteira, ou célula com centro (clique no mapa, local salvo ou subprefeitura) e raio de 2 a 30 km;
  - chuva das 72 h anteriores, de 0 a 300 mm.
- **FR-101 Chuva por setor.** O motor de simulação calcula, para cada setor:
  - a chuva máxima em 1 h e o total em 24 h, a partir do total, da duração e do padrão;
  - um fator espacial pela distância entre o ponto interno do setor e o centro da célula: 100% até o raio, caindo em linha reta até 0% em duas vezes o raio.

  O cálculo é feito na resolução de setor, não dos 12 pontos de previsão: uma célula de 5 km pode não atingir nenhum dos 12 pontos.
- **FR-102 Avaliação.** A chuva por setor entra no motor de risco existente, sem cópia de regras. A categoria, os fatores e a explicação são os mesmos da estimativa real.
- **FR-103 Presets.** Cenários prontos, cada um com a origem do número:

  | Preset | Cenário | Origem |
  |---|---|---|
  | Pancada de verão | 40 mm em 1 h, célula de 6 km | Faixa "forte" do motor (25–50 mm/h) |
  | Chuva persistente | 80 mm em 12 h, constante, cidade inteira, 30 mm nas 72 h anteriores | Faixa "forte" de 24 h do motor (60–100 mm) |
  | Solo encharcado | 30 mm em 3 h, cidade inteira, 100 mm nas 72 h anteriores | Gatilho de chuva antecedente do motor (≥ 50 mm) |
  | Extremo de referência | 136 mm em 24 h, concentrado, cidade inteira | Maior chuva diária da reanálise no centro desde 1991 (25/02/2010) |

- **FR-104 Execução e gravação.**
  - `POST /api/v1/simulation/runs` valida, calcula e grava.
  - A resposta traz o identificador, o resumo e a comparação com a estimativa real.
  - Os resultados ficam em tabelas próprias, nunca nas tabelas do risco real.
- **FR-105 Consulta.**
  - `GET /simulation/runs/{id}`: cenário, versões, resumo e comparação;
  - `GET /simulation/runs/{id}/sectors`: lista paginada e filtrável por categoria e subprefeitura;
  - `GET /simulation/runs/{id}/sectors/{sector_id}`: explicação;
  - `GET /map/layers/simulation/{id}`: GeoJSON para o mapa;
  - `GET /simulation/presets`.
- **FR-106 Comparação com o real.** Para cada execução, o sistema compara com a estimativa real mais recente:
  - contagem por categoria nos dois casos;
  - setores que sobem e que descem de categoria;
  - subprefeituras mais afetadas.

  Se a estimativa real estiver vencida, a comparação aparece com aviso.
- **FR-107 Página `/simulation`.**
  - formulário com os presets e o mapa (MapLibre, reaproveitando a Fase 4) para escolher o centro;
  - resultado: contagem por categoria, mapa dos setores, ranking, explicação ao clicar e comparação com o real;
  - link permanente `/simulation?execucao=<id>`;
  - estado de dados `simulation` (Constituição §11).

### Parte B
- **FR-108 Incerteza com seed.**
  - Até 100 variações. A intensidade varia ±u%, com u de 0 a 50. O centro da célula se desloca até s km, com s de 0 a 10.
  - O seed é um número inteiro, informado ou sorteado, e fica gravado.
  - Resultado por setor: categoria mais frequente, P(≥ alto) e P(crítico).
  - Resultado geral: média e faixa de 10% a 90% do número de setores em alto + crítico.
- **FR-109 Modo `HYBRID`.**
  - Parte da previsão real das próximas 24 h e das 72 h anteriores reais nos 12 pontos.
  - Ajustes possíveis: multiplicar a chuva prevista (de 50% a 300%), somar uma célula de chuva, ou os dois.
  - A execução grava o horário da previsão usada.
  - Se a previsão estiver `STALE` ou `UNAVAILABLE`, o `HYBRID` é recusado com explicação, sem trocar por outra fonte (Constituição §7.1).
- **FR-110 Histórico.**
  - `GET /simulation/runs`: últimas execuções, com cenário resumido.
  - "Repetir" reexecuta com os mesmos parâmetros e seed.
  - Se o motor de risco ou os setores tiverem mudado desde a execução original, o resultado novo vem com aviso.

## Requisitos não funcionais
- **NFR-100** O motor de simulação é puro, determinístico e testado sem banco, com um contrato do import-linter igual ao do risco e ao das análises. O gerador aleatório é `random.Random(seed)`, da biblioteca padrão, sem estado global.
- **NFR-101** Uma execução de 100 variações sobre os 793 setores responde em menos de 2 s no Docker local, sem worker. O tamanho máximo é validado antes do cálculo.
- **NFR-102** Retenção de 30 dias, com limpeza diária pelo agendador. No máximo 500 execuções guardadas; acima disso, as mais antigas saem primeiro.
- **NFR-103** Acessibilidade WCAG 2.2 AA: o formulário funciona sem o mapa (centro por subprefeitura ou local salvo), os resultados têm tabela e o aviso de simulação é lido por leitores de tela.

## Regras de negócio
- **BR-100 Identificação.**
  - Toda tela, mapa, popup, tabela e exportação de simulação traz a faixa **"SIMULAÇÃO — cenário hipotético, não é previsão nem alerta"**, com cor própria que não se confunde com as categorias de risco.
  - No modo `HYBRID`, a faixa diz "SIMULAÇÃO A PARTIR DA PREVISÃO REAL".
- **BR-101 Isolamento.**
  - Resultados simulados ficam em `simulation_runs` e `simulation_results`, com `kind = SIMULATED` e `mode = SIMULATION` ou `HYBRID`.
  - Nunca entram nas Análises, nos KPIs da Visão geral, na página de Risco nem nos alertas.
- **BR-102 Reprodutibilidade.** Cada execução grava:
  - parâmetros;
  - seed;
  - versão do motor de simulação (`simulation_engine_version`);
  - versão do motor de risco;
  - impressão digital (hash) dos dados dos setores usados.

  Mesmos parâmetros, seed, versões e impressão digital produzem o mesmo resultado, setor por setor.
- **BR-103 Sem dado faltante.** No modo `SIMULATION` toda a chuva vem do cenário, então não há categoria "desconhecido" por falta de chuva. No `HYBRID`, um ponto sem previsão deixa os setores dele como "desconhecido", como no real.
- **BR-104 Limites do cenário.** Os valores fora das faixas do FR-100 são recusados com 422 e explicação. A chuva de 1 h nunca passa do total.

## Critérios de aceite
- **AC-100** *Given* uma célula de 6 km centrada num setor R4, *When* simulo 40 mm em 1 h, *Then* esse setor sai como alto (chuva forte × suscetibilidade 4). *When* simulo 60 mm em 1 h, *Then* ele sai como crítico. Em ambos os casos, um setor a 20 km sai como baixo.
- **AC-101** *Given* o mesmo cenário, *When* simulo duas vezes, *Then* os resultados são idênticos, setor por setor.
- **AC-102** *Given* um preset, *When* abro a página, *Then* vejo o cenário e a origem do número antes de executar.
- **AC-103** *Given* uma execução, *When* abro a página de Risco, as Análises e a Visão geral, *Then* nenhum número delas mudou.
- **AC-104** *Given* 100 variações com seed 42, *When* repito, *Then* as probabilidades por setor são idênticas. *Given* seed 43, *Then* pelo menos uma probabilidade muda.
- **AC-105** *Given* previsão `STALE`, *When* peço `HYBRID`, *Then* recebo 409 com explicação, e o modo `SIMULATION` continua disponível.
- **AC-106** *Given* 120 variações ou 400 mm, *When* envio, *Then* recebo 422 com o limite.
- **AC-107** *Given* qualquer tela de resultado, *Then* a faixa de simulação está visível e é anunciada por leitor de tela (teste axe e de texto).

## Dependências
- Specs 004 (mapa) e 005 (motor de risco e setores).
- Previsão real da Open-Meteo (Parte B, `HYBRID`).

## Riscos e limitações
- **A simulação herda o motor v0:**
  - limites de chuva ainda não calibrados com eventos reais;
  - nenhuma hidrologia: a chuva caída num setor não escorre para outro.

  Cada tela lembra isso.
- **Padrões no tempo simplificados:** três formas fixas, não chuvas de projeto (Huff ou blocos alternados com curva IDF). Uma curva IDF de São Paulo pode substituí-los depois, com fonte.
- **Célula circular com borda linear:** uma aproximação didática, não um campo de chuva.
- **Links públicos:** qualquer pessoa com o link vê a simulação. Não há dado pessoal nela.
