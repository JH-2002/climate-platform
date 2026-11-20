# Spec 005 — Motor de risco de alagamento v0 (experimental)

> Status: **Aprovada** (2026-11-19) · Fase: 5 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md)

## Contexto
As fases 2–4 entregam previsão de chuva e um mapa. Falta responder **"onde a chuva prevista pode causar alagamento"**. O roteiro previa ANA e CGE como dependências, mas:
- a ANA exige cadastro e mede rios da região metropolitana, não alagamento urbano;
- o CGE não tem API pública.

O GeoSampa (Prefeitura de São Paulo) publica por WFS aberto, sem chave, as camadas que faltavam. O acesso foi testado em 2026-11-19 a partir da rede do responsável (ver [SOURCES.md §10](../../docs/data-sources/SOURCES.md)):

| Camada | Conteúdo | Tamanho |
|---|---|---|
| `risco_hidrologico` | Setores de risco hidrológico vistoriados pela Prefeitura: grau R1–R4, tipo de processo, moradias, subprefeitura, bacia | 793 polígonos, 1,6 MB |
| `area_inundavel` | Manchas de inundação de período de retorno 100 anos | 53 polígonos, 0,3 MB |
| `risco_ocorrencia_alagamento` / `risco_ocorrencia_inundacao` | Ocorrências registradas pela Defesa Civil (SIGRC) no ano corrente | 315 pontos cada, ~0,1 MB |

Com isso, o motor v0 cruza **onde a cidade já é suscetível** (dados oficiais) com **quanta chuva está prevista** (Open-Meteo). O resultado é um **risco estimado pelo sistema**, heurístico e não validado (Constituição §13). Não é um alerta oficial (§7, item 7).

## Objetivo
Para cada setor de risco hidrológico da capital, estimar a condição de alagamento nas próximas 24 h em quatro níveis (baixo, moderado, alto, crítico) ou "desconhecido", com explicação de cada fator. O resultado aparece no mapa, numa página de risco e via API.

## Escopo
**Incluído:**
- Sincronização das camadas do GeoSampa (setores, manchas, ocorrências).
- Grade de pontos de previsão cobrindo a capital.
- Motor de regras versionado (`risk_engine_version`), com execução horária gravada para auditoria.
- API de risco.
- Camada de risco no mapa.
- Página `/risk` com resumo, ranking e explicação.

**Fora do escopo:**
- Alertas oficiais do CGE e da Defesa Civil (sem API; ficam para quando houver acesso).
- Níveis de rio da ANA.
- Manchas de inundação de 5 e 25 anos (30 mil+ células cada; reavaliar com recorte por bacia).
- Notificações e e-mail.
- Calibração estatística com ocorrências históricas (exige anos anteriores; Fase 6/7).
- Observações do INMET no gatilho (entram quando o token chegar — FR-061 já prevê a substituição).

## User stories
- **US-050** Como morador, quero saber se a chuva prevista pode causar alagamento perto de mim.
- **US-051** Como analista, quero ver quais setores têm maior risco estimado agora e por quê.
- **US-052** Como gestor, quero que o risco estimado nunca seja confundido com um alerta oficial.
- **US-053** Como desenvolvedor, quero cada estimativa rastreável até os dados e a versão do motor que a geraram.

## Requisitos funcionais
- **FR-060** Job diário sincroniza as camadas do GeoSampa (setores, manchas 100 anos, ocorrências de alagamento e inundação). O job grava `ingestion_runs` e `raw_payloads`, é idempotente pela chave natural da fonte e mantém o último dado válido se a fonte falhar.
- **FR-061** Gatilho de chuva por setor, tomado do ponto de previsão mais próximo:
  - maior chuva horária prevista nas próximas 24 h (`P1h_max`);
  - chuva prevista acumulada em 24 h (`P24`);
  - chuva estimada nas 72 h anteriores (`A72`, `kind = MODELED`).

  Quando houver observações do INMET, `A72` passa a usar a estação mais próxima, com o tipo informado.
- **FR-062** A grade de previsão cobre a capital com pontos configuráveis (`FORECAST_POINTS`; padrão de 12 pontos em grade regular). A grade é coletada pelo job existente da Open-Meteo, que passa a pedir `past_days=3`.
- **FR-063** O motor calcula, para cada setor:
  - nível de chuva (0–3) (BR-060);
  - suscetibilidade (1–4) (BR-061);
  - categoria pela matriz (BR-062);
  - lista de fatores explicativos em português.
- **FR-064** Cada execução do motor grava:
  - versão do motor, horário, janela de validade e parâmetros;
  - horário da previsão usada e o frescor das entradas;
  - o resultado de cada setor.

  As execuções rodam de hora em hora, logo após a coleta da previsão, e também sob demanda pelo agendador ao iniciar.
- **FR-065** `GET /api/v1/risk/summary`: última execução, contagem por categoria, versão do motor, frescor das entradas e aviso de modelo experimental.
- **FR-066** `GET /api/v1/risk/areas?category=&subprefecture=&limit=`: lista de setores ordenada por categoria, chuva e moradias, com os fatores.
- **FR-067** `GET /api/v1/risk/areas/{id}`: detalhe do setor com fatores, entradas (valor, unidade, tipo, frescor, fonte), ocorrências próximas e link para a fonte oficial.
- **FR-068** `GET /api/v1/map/layers/risk`: FeatureCollection com os polígonos dos setores e a categoria. `GET /api/v1/map/layers/flood-occurrences`: pontos das ocorrências.
- **FR-069** Mapa: novas camadas "Risco estimado (setores)" e "Ocorrências registradas".
  - Cor da categoria sempre acompanhada de texto na legenda e no popup.
  - Em 3D, os setores são extrudados por categoria.
- **FR-070** Página `/risk`: faixa fixa "Estimativa experimental do sistema — não é alerta oficial. Em emergência, ligue 199 (Defesa Civil)", resumo por categoria, filtros (categoria, subprefeitura), tabela de setores e painel de explicação do setor.
- **FR-071** O painel do clima (`/weather`) mostra o risco do setor mais próximo, até 2 km, do local escolhido, com o mesmo aviso e um link para `/risk`.

## Requisitos não funcionais
- **NFR-060** O motor é uma função pura (entradas → resultados), testável sem banco. Coeficientes ficam num arquivo versionado, marcados `experimental`, com a origem documentada.
- **NFR-061** Uma execução completa (≈800 setores) termina em menos de 5 s no Docker local.
- **NFR-062** Os polígonos vão ao mapa simplificados (`ST_SimplifyPreserveTopology`, tolerância ~5 m) para manter a camada abaixo de 1 MB.
- **NFR-063** Atribuição "GeoSampa — Prefeitura de São Paulo" na legenda, no rodapé do mapa e na página `/risk`.

## Regras de negócio (coeficientes `experimental`, configuráveis)
- **BR-060 Nível de chuva:** maior entre os níveis de `P1h_max` e de `P24`, mais 1 se `A72 ≥ 50 mm` (solo encharcado e galerias cheias), com teto 3. O acréscimo só vale quando já há gatilho (nível ≥ 1): solo encharcado sem chuva prevista não cria risco.

  | Nível | `P1h_max` (mm/h) | `P24` (mm) |
  |---|---|---|
  | 0 — sem gatilho | < 10 | < 30 |
  | 1 — moderado | 10–25 | 30–60 |
  | 2 — forte | 25–50 | 60–100 |
  | 3 — muito forte | ≥ 50 | ≥ 100 |

  Origem: as faixas horárias seguem a classificação usual de intensidade de chuva (moderada até ~10 mm/h, forte acima, muito forte a partir de ~50 mm/h). Os limites de 24 h são provisórios e devem ser calibrados com ocorrências (Fase 6/7).
- **BR-061 Suscetibilidade:** grau oficial do setor (R1=1 … R4=4), mais 1 (teto 4) se o setor cruza uma mancha de inundação de 100 anos **ou** tem 2 ou mais ocorrências registradas a até 300 m nos últimos 12 meses.
- **BR-062 Matriz de risco** (linhas: nível de chuva; colunas: suscetibilidade):

  | | 1 | 2 | 3 | 4 |
  |---|---|---|---|---|
  | **0** | baixo | baixo | baixo | baixo |
  | **1** | baixo | baixo | moderado | moderado |
  | **2** | baixo | moderado | alto | alto |
  | **3** | moderado | alto | crítico | crítico |
- **BR-063 Desconhecido:** a categoria é "desconhecido" (cinza) se:
  - não há ponto de previsão a até 25 km;
  - a previsão está `STALE` ou `UNAVAILABLE`;
  - faltam mais de 2 horas na janela de 24 h.

  O motor nunca rebaixa um setor para "baixo" por falta de dado.
- **BR-064 Validade:** cada resultado vale de `computed_at` até `computed_at + 24 h` e informa o horário da previsão usada. Resultado com mais de 3 h é exibido como desatualizado.
- **BR-065 Separação de categorias:** a palavra "alerta" não aparece em rótulos do risco estimado. Os textos usam "risco estimado", "condição favorável a alagamento" e "estimativa experimental".

## Critérios de aceite
- **AC-060** *Given* a sincronização com respostas reais gravadas do GeoSampa, *When* o job roda duas vezes, *Then* não duplica setores nem ocorrências e registra a execução.
- **AC-061** *Given* um setor R3 com `P1h_max = 30 mm`, *When* o motor roda, *Then* a categoria é "alto" e os fatores citam "chuva forte prevista (30 mm em 1 h)" e "setor R3 vistoriado pela Prefeitura".
- **AC-062** *Given* um setor R2 que cruza mancha de 100 anos e `P24 = 70 mm`, *When* o motor roda, *Then* a suscetibilidade é 3 e a categoria é "alto".
- **AC-063** *Given* previsão `STALE`, *When* o motor roda, *Then* todos os setores ficam "desconhecido" com o motivo.
- **AC-064** *Given* `/risk`, *When* abro a página, *Then* vejo o aviso de estimativa experimental, o 199, a versão do motor e o horário da previsão usada.
- **AC-065** *Given* o mapa com a camada de risco, *When* clico num setor, *Then* vejo a categoria em texto, os fatores e o link para o detalhe.
- **AC-066** *Given* a mesma entrada, *When* o motor roda duas vezes, *Then* produz o mesmo resultado (determinístico) e grava duas execuções distintas.
- **AC-067** *Given* a busca de textos da interface, *Then* nenhum rótulo de risco estimado usa a palavra "alerta".

## Dependências
- Specs 002–004.
- GeoSampa WFS (`http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs`), testado em 2026-11-19.
- Open-Meteo com `past_days`.

## Riscos e limitações
- **Modelo não validado.** As faixas são heurísticas. A interface e a API dizem isso sempre. A calibração depende de séries de ocorrências de anos anteriores (disponíveis no GeoSampa só para download, não por WFS).
- **Previsão de modelo como gatilho.** Erros de previsão local de chuva convectiva são grandes. A estimativa indica condição favorável, não ocorrência.
- **Cobertura.** Os setores mapeados não cobrem toda a cidade; fora deles o sistema diz "fora de setor mapeado", não "baixo".
- **Licença.** O GeoSampa declara acesso sem restrições, mas os termos de licença não aparecem nos metadados. Registrar a atribuição e confirmar antes de uso público (Fase 8).
- **Fonte em HTTP.** O WFS não oferece HTTPS. Os dados são públicos e só de leitura, e o hash do conteúdo é gravado.
