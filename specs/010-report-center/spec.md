# Spec 010 — Central de relatórios

> Status: **Concluída** (2026-11-25) · Fase: 10 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md) · ADR: [ADR-015](../../docs/architecture/adr/ADR-015-report-center.md)

## Contexto
As Fases 3 a 9 mostram os dados na tela. Gestores, pesquisadores e jornalistas precisam **levar** esses dados: um PDF para anexar a um ofício, um CSV para a planilha, um JSON para outro sistema. Cada relatório tem que carregar a mesma rastreabilidade da tela: fonte, tipo do dado (medido, modelo, previsão, calculado, simulado), horário e os avisos de limitação (Constituição §7, §10 e §13).

A geração pode levar alguns segundos (os 793 setores, séries de 35 anos, os mapas), então roda em segundo plano, no worker, e a tela acompanha o andamento.

## Objetivo
Gerar, sob demanda e em segundo plano, relatórios em PDF, CSV e JSON a partir dos dados que a plataforma já tem, com fonte, tipo, horário e avisos em todos eles, e baixá-los por um link.

## Escopo
**Tipos de relatório**

| Código | Relatório | Conteúdo | Parâmetros |
|---|---|---|---|
| `situacao` | Situação agora | Alertas oficiais vigentes e próximos; estimativa de risco (resumo e setores em alto ou crítico); chuva prevista para 24 h por ponto; estado das fontes | — |
| `risco` | Risco por setor | Os setores de risco com categoria, grau, chuva prevista, fatores e terreno | subprefeitura (opcional) |
| `alertas` | Alertas do período | Alertas oficiais e do sistema, com o texto da fonte | período (até 90 dias) e categoria |
| `chuva` | Chuva do período | Série diária ou mensal de chuva de um ponto da reanálise, com a normal quando houver | ponto, período (até 35 anos), grão |
| `simulacao` | Simulação | Cenário, contagens, setores e comparação com a estimativa real, com a faixa de simulação em todas as páginas | id da simulação |

**Formatos**
- **PDF**: A4, título, sumário dos números, tabelas, gráfico simples quando couber, fontes e avisos no rodapé de cada página.
- **CSV**: a tabela principal do relatório (UTF-8 com BOM, separador `;`, vírgula decimal, para abrir direto no Excel em português), com linhas de comentário no topo (`#`) dizendo fonte, tipo, horário e aviso.
- **JSON**: todo o conteúdo, com um bloco `metadata` (tipo, parâmetros, horário, versões dos motores, fontes e avisos).

**Fluxo**
- `POST /reports` cria o pedido e devolve o id; o worker gera o arquivo; a tela consulta o andamento e oferece o download.
- O arquivo fica guardado por 7 dias e depois é apagado.
- Página **Relatórios** (`/reports`): escolher tipo, formato e parâmetros; ver os pedidos recentes deste navegador com o andamento; baixar.
- Atalhos "Gerar relatório" nas páginas de Risco, Alertas, Análises (chuva) e Laboratório (simulação), que abrem `/reports` já preenchida.

**Fora do escopo**
- Envio por e-mail ou agendamento de relatórios (exige contas; Fase 11 ou depois).
- Relatório com mapa em imagem de satélite ou tiles de terceiros (licença de redistribuição). O PDF usa só desenhos próprios (barras e linhas).
- Editor de modelos de relatório.

## User stories
- **US-100** Como gestor, quero um PDF da situação de agora para anexar a um comunicado, com as fontes e os avisos.
- **US-101** Como analista, quero o CSV dos 793 setores com a categoria e os fatores, para trabalhar na planilha.
- **US-102** Como pesquisador, quero o JSON da série de chuva de um ponto, com os metadados, para outro sistema.
- **US-103** Como jornalista, quero o histórico dos alertas oficiais de um período, com o texto original.
- **US-104** Como analista, quero o relatório de uma simulação sem risco de ele ser confundido com dado real.

## Requisitos funcionais
- **FR-150 Pedido.** `POST /reports` com `{type, format, params}`: valida os parâmetros (422 com a mensagem em português), grava o pedido como `QUEUED` e enfileira a geração. Devolve `{id, status, links}`.
- **FR-151 Geração.** Uma tarefa do worker monta o conteúdo a partir dos serviços já existentes (nada de consulta duplicada), escreve o arquivo no formato pedido e guarda bytes, tamanho, hash SHA-256 e tipo MIME. Estados: `QUEUED` → `RUNNING` → `DONE` ou `FAILED` (com a mensagem). Pedido parado em `RUNNING` há mais de 10 min vira `FAILED`.
- **FR-152 Consulta e download.**
  - `GET /reports/{id}`: estado, título, parâmetros, tamanho e horários.
  - `GET /reports/{id}/download`: o arquivo, com nome descritivo (`situacao_2026-11-25_1430.pdf`) e `Content-Disposition: attachment`. 404 se não existe, 409 se ainda não terminou, 410 se expirou.
  - `GET /reports?ids=a,b,c`: os pedidos deste navegador (a lista de ids fica no navegador; não há contas).
  - `GET /reports/types`: os tipos, formatos e parâmetros aceitos, para a tela.
- **FR-153 Conteúdo comum.** Todo relatório traz: título; horário de geração (Brasília); parâmetros; para cada bloco de dados, a fonte, o tipo (`OBSERVED`, `FORECAST`, `MODELED`, `DERIVED`, `SIMULATED`) e o frescor; as atribuições de licença; os avisos que a tela mostra (risco experimental, alerta oficial só pela fonte, simulação).
- **FR-154 Simulação.** O relatório `simulacao` traz "SIMULAÇÃO — CENÁRIO HIPOTÉTICO, NÃO É PREVISÃO NEM ALERTA" no topo de todas as páginas do PDF, na primeira linha do CSV e em `metadata.mode = "SIMULATION"` no JSON. O nome do arquivo começa com `simulacao_`.
- **FR-155 Retenção.** Tarefa diária apaga os arquivos com mais de 7 dias (o registro do pedido fica, como `EXPIRED`).
- **FR-156 Página `/reports`.** Formulário com tipo, formato e parâmetros; lista dos pedidos deste navegador (andamento a cada 3 s enquanto houver pedido em aberto); download; estados de erro e expirado. Parâmetros iniciais pela URL (`?tipo=risco&subprefeitura=PENHA`).

## Requisitos não funcionais
- **NFR-150** O PDF é escrito por um módulo próprio e puro (`app/reports/pdf.py`), só com a biblioteca padrão: fontes padrão do PDF (Helvetica, com as larguras das métricas da Adobe) em WinAnsi, que cobre os acentos do português. Nenhuma dependência nova nem rebuild da imagem.
- **NFR-151** Os arquivos ficam no banco (`bytea`), com teto de 20 MB por arquivo: nenhum volume novo no Docker.
- **NFR-152** Limite de pedidos: no máximo 30 por hora no total e 5 em aberto ao mesmo tempo (429 com mensagem em português).
- **NFR-153** Gerar o `situacao` em PDF leva menos de 10 s; o `risco` com 793 setores, menos de 20 s.
- **NFR-154** O CSV abre no Excel em português sem ajuste (BOM, `;`, vírgula decimal) e escapa fórmulas (células que começam com `=`, `+`, `-` ou `@` ganham `'` na frente).

## Regras de negócio
- **BR-150 Mesmos números da tela.** O relatório usa os mesmos serviços da API; um número no PDF é o mesmo que a tela mostrou no mesmo horário.
- **BR-151 Tipo de dado sempre visível.** Nenhum valor de previsão ou modelo aparece como medição; cada tabela diz o tipo no título.
- **BR-152 Alertas.** O texto oficial vai como a fonte escreveu, com a fonte e a vigência. Alertas do sistema vão numa seção própria com o aviso de que não são alertas oficiais.
- **BR-153 Atribuições.** Open-Meteo (CC BY 4.0), INMET, GeoSampa, Copernicus, IAG/USP, Defesa Civil (IDAP), conforme os dados usados.

## Critérios de aceite
- **AC-150** *Given* um pedido `situacao` em PDF, *When* o worker termina, *Then* o status é `DONE`, o arquivo abre como PDF válido, cita as fontes e o aviso de risco experimental em todas as páginas, e o download tem o nome descritivo.
- **AC-151** *Given* o relatório `risco` em CSV, *Then* tem uma linha por setor ativo, abre com `;` e vírgula decimal, e as linhas de comentário dizem fonte, tipo e horário.
- **AC-152** *Given* uma simulação, *When* gero o relatório, *Then* a faixa de simulação está em todas as páginas do PDF, na primeira linha do CSV e em `metadata.mode` no JSON.
- **AC-153** *Given* parâmetros inválidos (período acima do limite, subprefeitura inexistente, simulação inexistente), *Then* 422 com mensagem e nenhum pedido criado.
- **AC-154** *Given* um arquivo com mais de 7 dias, *When* a limpeza roda, *Then* o download responde 410 e o pedido aparece como expirado.
- **AC-155** *Given* um valor de texto vindo da fonte que começa com `=`, *Then* o CSV o escreve como texto (`'=`).
- **AC-156** *Given* a página `/reports`, *When* peço um relatório, *Then* vejo o andamento e o botão de download quando termina, e o pedido continua na lista depois de recarregar.

## Dependências
- Specs 005 (risco), 006 (análises), 007 (simulação) e 009 (alertas).
- Nenhuma biblioteca nova.

## Riscos e limitações
- **PDF simples.** Sem fontes embutidas nem imagens de mapa: é um documento de texto, tabelas e gráficos de barras. Suficiente para anexar e imprimir; um layout mais rico fica para depois.
- **Sem contas.** Qualquer pessoa com o id baixa o arquivo. Os relatórios só contêm dados públicos já mostrados na tela, e o id é um UUID aleatório.
- **Arquivos no banco.** Com o teto de 20 MB e 7 dias de retenção, o volume fica pequeno; se crescer, a migração para arquivos em volume é direta.
