# Spec 003 — Painel do clima

> Status: **Concluída** (2026-11-19) — medições aguardam o token do INMET · Fase: 3 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md)

## Contexto
A Fase 2 coleta a previsão da Open-Meteo e o cadastro de estações do INMET. As observações medidas pelas estações dependem de um token do INMET que ainda não chegou. O usuário cotidiano precisa responder rápido: *como está o tempo agora, vai chover, e quanto?* — sem ser induzido a tomar estimativa por medição.

## Objetivo
Entregar a página **Clima** (`/weather`) com estimativa para a hora atual, previsão de 48 h e de 7 dias, chuva prevista acumulada, estações próximas e locais salvos, deixando explícito o que é previsão de modelo e o que é medição.

## Escopo
**Incluído:** endpoint de previsão por coordenada; página `/weather`; gerenciamento de locais no navegador; seção de estações próximas com a disponibilidade das observações.

**Fora do escopo:** observações medidas e acumulados medidos (dependem do token — entram junto com a T020 da spec 002); contas de usuário e sincronização de locais entre dispositivos (Fase de usuários); alertas (Fase 9); mapa (Fase 4).

## User stories
- **US-030** Como usuário, quero ver as condições estimadas para agora no meu local, sabendo que é estimativa.
- **US-031** Como usuário, quero ver a previsão das próximas 48 h e dos próximos 7 dias.
- **US-032** Como usuário, quero saber quanta chuva está prevista nas próximas horas.
- **US-033** Como usuário, quero salvar locais (casa, trabalho) e alternar entre eles.
- **US-034** Como usuário, quero ver as estações oficiais próximas e se há medições disponíveis.

## Requisitos funcionais
- **FR-040** `GET /api/v1/weather/forecast?lat&lon` responde com o ponto de previsão coletado mais próximo (até 25 km), sua distância e a fonte com frescor e atribuição.
- **FR-041** A resposta traz `now`: valores da hora atual da previsão horária, marcados `kind = FORECAST` e descritos como estimativa de modelo.
- **FR-042** A resposta traz a série horária das próximas 48 h (temperatura, chuva, umidade, vento) e a diária dos próximos 7 dias (máx./mín., chuva total, probabilidade máxima de chuva).
- **FR-043** A resposta traz a chuva **prevista** acumulada em 1, 3, 24 e 72 h, informando se o intervalo está completo (todas as horas presentes) e quantas horas havia.
- **FR-044** Sem ponto de previsão até 25 km, a API responde 404 Problem Details explicando que não há previsão coletada para o local.
- **FR-045** A página `/weather` permite escolher entre locais salvos; adicionar local por nome + coordenadas ou pela geolocalização do navegador (mediante permissão); remover; e definir um local padrão. Os locais ficam neste navegador.
- **FR-046** A página mostra as estações do INMET em até 30 km e, para cada uma, a disponibilidade das observações (hoje: indisponível por falta de token).
- **FR-047** Todo valor exibido indica unidade, e toda seção indica se é previsão de modelo ou medição, com fonte e horário da coleta.
- **FR-048** O local selecionado fica na URL (`?lat=&lon=&nome=`) para a página poder ser compartilhada.

## Requisitos não funcionais
- **NFR-040** `/weather/forecast` responde em < 300 ms localmente.
- **NFR-041** Gráfico com alternativa textual (tabela acessível) e sem depender só de cor.
- **NFR-042** Funciona em celular (layout em coluna única).

## Regras de negócio
- **BR-040** "Agora" = previsão para a hora cheia corrente (UTC). Se essa hora não estiver na série, não há valor "agora".
- **BR-041** Acumulado previsto de N horas soma as N horas a partir da hora corrente; `complete = false` se faltar alguma, e o valor exibido vem acompanhado do aviso.
- **BR-042** Dias da previsão diária seguem o horário de Brasília (a coleta pede `timezone=America/Sao_Paulo`).
- **BR-043** Previsão nunca é apresentada como medição; a seção de medições mostra "indisponível" com o motivo enquanto não houver observações.

## Critérios de aceite
- **AC-040** *Given* previsão coletada para o centro de SP, *When* consulto `/weather/forecast` para a Av. Paulista, *Then* recebo ponto a < 25 km, `now`, 48 itens horários (ou menos, se a série acabar antes), 7 dias e 4 acumulados.
- **AC-041** *Given* um local a 300 km de qualquer ponto coletado, *When* consulto, *Then* recebo 404 Problem Details.
- **AC-042** *Given* a série horária com uma hora faltando no período de 3 h, *When* calculo o acumulado de 3 h, *Then* `complete = false` e `hours_available = 2`.
- **AC-043** *Given* a página aberta, *When* adiciono um local e recarrego, *Then* o local continua na lista; *When* o removo, *Then* some.
- **AC-044** *Given* a página aberta, *When* olho a seção "Agora", *Then* vejo o rótulo de estimativa de modelo, a fonte e o horário da coleta.
- **AC-045** *Given* a API indisponível, *When* abro `/weather`, *Then* vejo erro compreensível e "Tentar novamente".

## Estados
Carregando, sucesso, sem previsão para o local (404), erro, sem conexão, dados atrasados/desatualizados (frescor ≠ FRESH mostra aviso).

## Dependências
Spec 002 (previsão e estações coletadas). Recharts (gráfico).

## Riscos e limitações
- Previsão de modelo global/regional não representa bem tempestades locais intensas — aviso fixo na página.
- Locais salvos só neste navegador até existir conta de usuário.
