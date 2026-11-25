# Spec 006 — Análises (Analytics)

> Status: **Concluída** (2026-11-20) · Fase: 6 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md)

## Contexto
O documento mestre (§13) pede, para esta fase:
- KPIs e um painel executivo;
- análises de chuva, de risco, das estações e de tendências históricas;
- um Analytics Studio, um Data Explorer e insights automáticos.

Tudo isso precisa sair de dados armazenados, sem métricas fixas no código.

**O que o sistema tem hoje:**
- previsão de 7 dias e as 72 h anteriores em 12 pontos (modelo);
- risco estimado de hora em hora desde a Fase 5;
- 630 ocorrências de 2026 (GeoSampa);
- histórico das coletas.

Não há medições: o token do INMET não chegou. Também não há série longa. Sem uma série longa, "acima do normal", percentis e tendências seriam inventados.

**Duas fontes testadas em 2026-11-19 resolvem isso** (ver [SOURCES.md §11–12](../../docs/data-sources/SOURCES.md)):

| Fonte | O que é | Tipo | Período | Observação |
|---|---|---|---|---|
| **Chuva mensal do IAG/USP (Água Funda)**, publicada pela Prefeitura (SMUL/Geoinfo) | Total mensal medido no pluviômetro da estação do IAG/USP | `OBSERVED` | 1933–2025, sem falhas | Revisada com o IAG em 2025; normal 1991–2020 publicada: 1.559,2 mm/ano |
| **Open-Meteo Historical (reanálise ERA5/ERA5-Land)** | Chuva diária e temperaturas máxima, mínima e média por ponto | `MODELED` | 1991 até ontem | Chuva em células de ~25 km: os 12 pontos viram cerca de 4 séries distintas. No centro, ~1.366 mm/ano em 1991–2020, ~12% abaixo da normal medida |

## Objetivo
Responder, com números rastreáveis:
- O que está acontecendo?
- Onde?
- O que pode acontecer nas próximas horas?
- Quais regiões merecem atenção?
- Os dados são confiáveis?

E permitir explorar os dados sem que a interface invente conclusões.

## Escopo
Dividido em duas partes, entregues e validadas em sequência.

**Parte A — base analítica e visão geral**
- Motor analítico puro (`app/analytics/`):
  - estatísticas descritivas;
  - agregações por hora, dia, semana, mês e ano;
  - comparações entre períodos;
  - climatologia e anomalia;
  - regras de insight.
- Ingestão das duas fontes novas.
- Catálogo de conjuntos de dados (Data Explorer) com metadados e estatísticas.
- Painel executivo na **Visão geral** (`/`), com KPIs e insights automáticos.

**Parte B — áreas de análise**
- **Análises de chuva** (`/analytics`, aba Chuva): mensal e anual frente à normal, distribuição, extremos, sazonalidade e chuva × ocorrências.
- **Tendências históricas** (IAG/USP 1933–2025): totais anuais, média móvel de 10 anos e comparação entre as normais 1933–1960, 1961–1990 e 1991–2020.
- **Risco**: evolução das categorias por execução e distribuição por subprefeitura e bacia.
- **Fontes e estações**: disponibilidade, atraso, taxa de falhas, dados ausentes e cobertura.
- **Analytics Studio**: conjunto de dados, local, período, variável, agregação, comparação e visualização compatível; exportação em CSV.

**Fora do escopo**
- Análises com observações horárias do INMET (entram quando o token chegar; o catálogo já as prevê).
- Divergência entre estações (só há duas na capital, e sem medições).
- Nível de rio (ANA).
- Texto gerado por IA: os insights são frases-modelo preenchidas com métricas.
- Mapas de calor espaciais: com ~4 células distintas de reanálise, seriam enganosos.
- Testes estatísticos de tendência (Mann-Kendall etc.): mostramos variação entre normais e médias móveis, sem atribuir causa.

## User stories
- **US-060** Como morador, quero abrir a plataforma e entender em segundos se há algo que mereça atenção.
- **US-061** Como analista, quero comparar a chuva de um mês com a normal e ver se ela foi incomum.
- **US-062** Como pesquisador, quero ver a série histórica longa e as normais, sem conclusões apressadas sobre mudança climática.
- **US-063** Como analista, quero montar uma consulta (dados, local, período, agregação) e exportar o resultado.
- **US-064** Como operador, quero saber se as fontes estão em dia e com que taxa de falhas.
- **US-065** Como qualquer usuário, quero saber de onde vem cada número e de que tipo ele é (medido, modelo, previsão, calculado).

## Requisitos funcionais
### Parte A
- **FR-080** Importador da chuva mensal do IAG/USP:
  - lê um CSV versionado no repositório (`data/reference/`), extraído da página da Prefeitura por um script que confere a soma dos meses com o total anual;
  - grava a série com proveniência (URL, data da extração, hash);
  - é idempotente.
- **FR-081** Ingestão da reanálise diária da Open-Meteo para os pontos da grade:
  - carga inicial desde 1991, um ponto por vez, respeitando o limite de uso;
  - depois, atualização diária dos últimos 10 dias, porque os dias recentes são revisados pela fonte;
  - variáveis: chuva, temperatura máxima, mínima e média.
- **FR-082** Catálogo `GET /api/v1/analytics/datasets`. Cada conjunto tem:
  - id, nome, descrição, fonte, licença e atribuição, tipo (`OBSERVED`, `MODELED`, `FORECAST`, `DERIVED`);
  - resolução temporal e espacial, período coberto, locais;
  - variáveis com unidade, quantidade de registros, dados ausentes e frescor.
- **FR-083** `GET /api/v1/analytics/datasets/{id}/describe?variable=&location=&start=&end=` devolve: n, ausentes, média, mediana, mínimo, máximo, desvio padrão, percentis 5/25/75/95 e valores atípicos (regra 1,5×IQR, com a quantidade e os 10 maiores).
- **FR-084** `GET /api/v1/analytics/kpis` devolve os indicadores do painel executivo. Cada um traz valor, unidade, período, tipo, fonte e frescor:
  - chuva prevista para as próximas 24 h (maior ponto e média);
  - chuva do mês até ontem frente à normal do mês proporcional aos dias (reanálise);
  - setores em risco alto ou crítico, agora e há 24 h;
  - ocorrências nos últimos 30 dias;
  - fontes em dia e fontes com problema;
  - taxa de falhas das coletas em 7 dias.
- **FR-085** `GET /api/v1/analytics/insights` devolve os insights ativos das regras documentadas (BR-080). Cada insight traz:
  - código da regra, severidade (`info` ou `atencao`) e texto;
  - as métricas usadas, com valor, limite e período;
  - fontes e tipos.
- **FR-086** Visão geral (`/`) vira o painel executivo:
  - **Agora:** estimativa do tempo e chuva prevista;
  - **Atenção:** insights;
  - **Onde:** setores de maior risco e ocorrências recentes;
  - **Confiabilidade:** saúde das fontes;
  - KPIs clicáveis, que levam à análise correspondente.

### Parte B
- **FR-087** `GET /api/v1/analytics/series`. Parâmetros:
  - `dataset`, `variable`, `location`, `start`, `end`;
  - `grain` (`day`, `week`, `month`, `year`) e `agg` (`sum`, `mean`, `min`, `max`, `count`);
  - opcional `compare=normal|previous_period|same_period_last_year`.

  Devolve a série com tipo, unidade e cobertura de cada ponto (proporção de dados presentes no intervalo). Agregações incompatíveis com a variável (ex.: soma de temperatura) são recusadas com mensagem.
- **FR-088** `GET /api/v1/analytics/climatology?dataset=&variable=&location=&period=1991-2020`: média mensal e percentis por mês, com o número de anos usados.
- **FR-089** `GET /api/v1/analytics/series.csv`: mesmos parâmetros que FR-087, em CSV UTF-8 com cabeçalho de metadados (fonte, tipo, atribuição, consulta, horário).
- **FR-090** Aba **Chuva**:
  - mês a mês do ano corrente frente à normal;
  - totais anuais;
  - distribuição dos dias de chuva;
  - 10 maiores chuvas diárias;
  - sazonalidade (média mensal com faixa p25–p75);
  - chuva mensal × ocorrências mensais de 2026.

  Fonte e tipo aparecem em cada gráfico.
- **FR-091** Aba **Tendências**:
  - totais anuais do IAG/USP 1933–2025 com média móvel de 10 anos;
  - as três normais calculadas pelo sistema, comparadas com as publicadas;
  - anos mais chuvosos e mais secos.

  Texto fixo: "variação entre normais não indica, sozinha, a causa".
- **FR-092** Aba **Risco**: evolução, execução a execução, da contagem de setores por categoria (últimos 7 dias) e distribuição por subprefeitura e por bacia na última execução.
- **FR-093** Aba **Fontes e dados**, por fonte:
  - disponibilidade (execuções bem-sucedidas / total, 7 e 30 dias);
  - duração média das coletas;
  - atraso atual;
  - taxa de registros rejeitados;
  - última falha;
  - cobertura (pontos, estações, setores).
- **FR-094** **Analytics Studio**:
  - seletores de conjunto, variável, local, período, agregação e comparação, todos refletidos na URL;
  - a lista de visualizações depende do conjunto: linha e barra para séries, histograma e caixa para distribuição, calendário só com dados diários, ranking para locais;
  - tabela com os mesmos dados (acessível) e botão Exportar CSV.
- **FR-095** **Data Explorer** (`/analytics/datasets`): lista e ficha de cada conjunto (FR-082/FR-083).

## Requisitos não funcionais
- **NFR-080** O motor analítico é puro e testado sem banco. As consultas agregam no PostgreSQL (`date_trunc`) e trazem ao Python só o necessário.
- **NFR-081** `series` com até 35 anos diários responde em menos de 1 s no Docker local. As respostas usam cabeçalho de cache de 10 min.
- **NFR-082** A carga inicial da reanálise não estoura o limite gratuito da Open-Meteo (10 mil chamadas/dia; uma consulta longa conta como várias). Um ponto por vez, com pausa entre pontos e retomada de onde parou.
- **NFR-083** Gráficos com alternativa em tabela e descrição textual (WCAG 2.2 AA). Nenhum KPI sem fonte (Constituição §11).

## Regras de negócio
- **BR-080 Regras de insight** (limites `experimental`, versionados em `analytics/rules.py`):

  | Código | Condição | Severidade | Texto-modelo |
  |---|---|---|---|
  | IN-01 | Chuva prevista em 24 h num ponto ≥ p95 das chuvas diárias do mesmo mês na reanálise 1991–2020 daquele ponto | atenção | "Chuva prevista de {v} mm em 24 h na região {r}, acima de 95% dos dias de {mês} desde 1991 (p95 = {p} mm)." |
  | IN-02 | Chuva do mês até ontem ≥ 150% ou ≤ 50% da normal proporcional (reanálise, mesmo ponto), com ao menos 10 dias no mês | info | "{mês} acumula {v} mm até ontem, {x}% da média para o período (reanálise)." |
  | IN-03 | Dias seguidos sem chuva (< 1 mm) até ontem ≥ p90 das maiores sequências secas do mesmo mês (1991–2020) | info | "{n} dias seguidos sem chuva relevante, sequência maior que 90% das registradas em {mês} desde 1991." |
  | IN-04 | Setores alto + crítico agora − há 24 h ≥ 10, ou de 0 para ≥ 1 | atenção | "Setores com risco estimado alto ou crítico passaram de {a} para {b} nas últimas 24 h." |
  | IN-05 | Fonte com frescor `DELAYED`, `STALE` ou `UNAVAILABLE` por falha (credencial ausente vira só nota) | atenção | "{fonte}: {estado} desde {quando}." |
  | IN-06 | Uma subprefeitura concentra ≥ 25% das ocorrências dos últimos 90 dias (mínimo de 10 ocorrências no total) | info | "{subprefeitura} concentra {x}% das {n} ocorrências registradas nos últimos 90 dias." |

- **BR-081 Normal:**
  - reanálise: média de 1991–2020 do mesmo ponto;
  - IAG/USP: normais calculadas pelo sistema a partir dos totais mensais, comparadas com as publicadas pela Prefeitura (diferença ≤ 0,5 mm esperada).

  Uma normal só é exibida com ao menos 25 dos 30 anos presentes.
- **BR-082 Separação de tipos:** séries de tipos diferentes podem aparecer juntas no Studio, mas nunca são somadas nem comparadas como se fossem a mesma grandeza. A diferença de nível entre a reanálise e o IAG é explicada na ficha do conjunto.
- **BR-083 Clima × tempo:** os textos distinguem tempo (horas e dias), variabilidade (meses e anos) e clima (normais de 30 anos). Nenhuma tela afirma tendência climática a partir de menos de 30 anos.
- **BR-084 Cobertura:** um ponto agregado com cobertura < 80% é marcado como parcial. Com cobertura < 50%, o valor não é exibido; aparece "dados insuficientes".

## Critérios de aceite
- **AC-080** *Given* o CSV do IAG/USP, *When* importo, *Then* a soma dos 12 meses confere com o total anual publicado em todos os 93 anos, e as normais 1991–2020 calculadas ficam a até 0,5 mm das publicadas.
- **AC-081** *Given* a resposta real gravada da reanálise, *When* a carga roda duas vezes, *Then* não há duplicatas e a execução fica registrada.
- **AC-082** *Given* uma série com valores atípicos conhecidos, *When* peço `describe`, *Then* média, mediana, percentis e atípicos batem com o cálculo de referência.
- **AC-083** *Given* chuva prevista acima do p95 do mês, *When* consulto insights, *Then* aparece IN-01 com o valor, o limite e as fontes. *Given* chuva abaixo, *Then* IN-01 não aparece.
- **AC-084** *Given* a Visão geral, *When* abro, *Then* cada KPI mostra fonte, tipo e horário, e leva à análise correspondente.
- **AC-085** *Given* temperatura com `agg=sum`, *When* consulto `series`, *Then* recebo 422 com explicação.
- **AC-086** *Given* um conjunto mensal, *When* abro o Studio, *Then* o calendário não aparece entre as visualizações.
- **AC-087** *Given* a exportação CSV, *When* baixo, *Then* o arquivo traz fonte, tipo e atribuição no cabeçalho e os mesmos números da tela.
- **AC-088** *Given* a aba Tendências, *Then* vejo as três normais, a média móvel e o aviso sobre causa, sem nenhuma frase de tendência climática.

## Dependências
- Specs 002–005.
- Página da Prefeitura com a chuva do IAG/USP (testada em 2026-11-19).
- Open-Meteo Historical API (testada em 2026-11-19 pela rede do responsável: 35 anos diários em ~11 s por ponto).

## Riscos e limitações
- **Reanálise não é medição.**
  - A chuva da reanálise subestima temporais locais (máximo diário no centro: 136 mm) e fica ~12% abaixo da normal medida.
  - Serve para comparar um período com ele mesmo (anomalias no mesmo ponto), não para valores absolutos.
  - A interface diz isso em cada gráfico.
- **Uma só estação longa.** O IAG/USP representa a zona sul (Água Funda), não a cidade inteira. Isso fica explícito.
- **Ocorrências só de 2026 via WFS.** A comparação chuva × ocorrência cobre meses, não anos, e não é tratada como causalidade.
- **Página da Prefeitura sem API.** A atualização do CSV do IAG é anual e manual (script assistido), com conferência das somas.
- **Licenças.**
  - Open-Meteo: CC BY 4.0, uso não comercial.
  - IAG/USP via Prefeitura: dado público; termos não informados. A atribuição é registrada e exibida.
