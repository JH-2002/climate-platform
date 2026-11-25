# Spec 002 — Weather Data Ingestion (INMET + Open-Meteo)

> Status: **Concluída, exceto observações horárias do INMET (aguardando token)** (2026-11-19) · Fase: 2 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md)

## Contexto
A plataforma precisa de observações reais e previsão para alimentar dashboard, mapa e risco. As fontes foram avaliadas em `docs/data-sources/SOURCES.md`.

## Objetivo
Coletar, validar, normalizar e persistir observações horárias de estações automáticas do INMET na região piloto e previsão de 7 dias da Open-Meteo, com proveniência, frescor e qualidade rastreáveis.

## Escopo
**Incluído:** catálogo de fontes (`data_sources`); cadastro de estações INMET da região; ingestão horária de observações; ingestão de previsão; `ingestion_runs` e `raw_payloads`; checagens de qualidade básicas; cálculo de frescor; endpoints `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations`.

**Fora do escopo:** CEMADEN (importador de CSV vira spec 002b); ANA; interface de dashboard (spec 003); acumulados de chuva (spec 003); alertas.

## User stories
- **US-010** Como operador, quero saber quando cada fonte foi coletada com sucesso pela última vez para avaliar a confiabilidade.
- **US-011** Como analista, quero consultar a série de observações de uma estação num período para análise.
- **US-012** Como usuário, quero encontrar as estações mais próximas de um ponto.

## Requisitos funcionais
- **FR-020** O sistema registra cada fonte em `data_sources` com licença, método de acesso, intervalo esperado e limite de staleness.
- **FR-021** Uma tarefa sincroniza a lista de estações INMET (`/estacoes/T`) diariamente, filtrando pela região configurada, sem apagar estações que somem da lista (marca `status = INACTIVE`).
- **FR-022** Uma tarefa horária coleta observações das estações ativas para a janela das últimas N horas (padrão 6 h, cobrindo atrasos).
- **FR-023** Cada execução grava `ingestion_runs` com contagens de recebidos/inseridos/rejeitados e status `SUCCESS`, `PARTIAL` ou `FAILED`.
- **FR-024** Todo payload bruto é salvo em `raw_payloads` com hash; payload idêntico não é duplicado.
- **FR-025** A inserção é idempotente pela chave `(station_id, variable, observed_at)`.
- **FR-026** Valores são convertidos para unidades canônicas (Constituição §8) e horários para UTC.
- **FR-027** Checagens de qualidade marcam `quality_flag`: faixa física, timestamp no futuro (> 10 min), valor constante por ≥ 6 h (exceto chuva = 0), campo obrigatório ausente.
- **FR-028** Sem `INMET_TOKEN`, a coleta de observações não roda; `/sources/status` reporta `inmet` como `UNAVAILABLE` com motivo `missing_credentials`.
- **FR-029** A previsão Open-Meteo é coletada por célula de grade com cache de 60 min e gravada com `kind = FORECAST`.
- **FR-030** `/sources/status` retorna para cada fonte: `freshness` (`FRESH`/`DELAYED`/`STALE`/`UNAVAILABLE`/`UNKNOWN`), `last_success_at`, `last_run_status`, licença/atribuição.
- **FR-031** `/stations/nearby` usa PostGIS (`ST_DWithin` em `geography`) e retorna distância em km.
- **FR-032** A página `/status` do frontend mostra, para cada fonte, frescor, motivo, última coleta bem-sucedida e atribuição/licença. *(Adicionada em 2026-11-19 — ver plan.md.)*

## Requisitos não funcionais
- **NFR-020** Timeout de 15 s por requisição; até 3 tentativas com backoff exponencial + jitter; circuit breaker abre após 5 falhas consecutivas por 10 min.
- **NFR-021** Respeitar limites da Open-Meteo (Constituição §10, ADR-004).
- **NFR-022** O token nunca aparece em logs (path mascarado).
- **NFR-023** `/stations/{id}/observations` responde em < 300 ms para 30 dias × 10 variáveis (local).

## Regras de negócio
- **BR-020** Frescor: `FRESH` se `now - last_observed_at ≤ 1,5 × intervalo esperado`; `DELAYED` até 3×; `STALE` acima; `UNAVAILABLE` se a última execução falhou ou não há credencial; `UNKNOWN` se nunca coletou.
- **BR-021** Dados de previsão nunca preenchem lacunas de observação.
- **BR-022** Valores marcados `FAILED` não entram em agregados, mas permanecem consultáveis com o filtro `include_flagged=true`.

## Critérios de aceite (resumo — detalhar no plan)
- **AC-020** *Given* resposta gravada do INMET com 24 horas para A701, *When* a ingestão roda duas vezes, *Then* o número de linhas é o mesmo após a segunda execução.
- **AC-021** *Given* `INMET_TOKEN` ausente, *When* consulto `/sources/status`, *Then* `inmet.freshness = "UNAVAILABLE"` e `reason = "missing_credentials"`.
- **AC-022** *Given* temperatura de 80 °C no payload, *When* normalizada, *Then* é gravada com `quality_flag = "FAILED"` e o motivo fica registrado.
- **AC-023** *Given* a fonte retornando 500 em 5 execuções, *When* a sexta é agendada, *Then* o circuit breaker impede a chamada e o run é gravado como `FAILED` com `circuit_open`.
- **AC-024** *Given* um ponto na Av. Paulista, *When* chamo `/stations/nearby?radius_km=30`, *Then* recebo estações ordenadas por distância com `distance_km`.

## Dependências
Spec 001 concluída; token INMET; resultado do smoke test T014.

## Riscos
- **R-020** Token do INMET pode demorar ou ser negado → a fase entrega toda a pipeline testada com fixtures e Open-Meteo real; observações ficam `UNAVAILABLE` até o token chegar.
- **R-021** Formato da API do INMET pode diferir do documentado por terceiros → adapter só é escrito após a T014 registrar respostas reais.
- **R-022** Poucas estações INMET na capital → cobertura espacial limitada; CEMADEN (002b) complementa.
