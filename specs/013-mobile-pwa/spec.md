# Spec 013 — Celular e app instalável

> Status: **Em andamento** (2026-11-25) · Fase: 13 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md)

## Contexto
A plataforma e a vitrine pública (spec 012) funcionam no computador, mas no celular o menu
lateral vira uma lista de 11 links antes do conteúdo: quem abre um alerta pelo telefone precisa
rolar a tela inteira para chegar ao que importa. A plataforma também não pode ser instalada na
tela inicial e não mostra nada sem conexão.

## Objetivo
Uso confortável no celular: menu recolhível, sem rolagem lateral, app instalável (PWA) e, sem
conexão, as últimas telas e dados vistos, com aviso claro de que podem estar desatualizados.

## Escopo
- Menu recolhível em telas estreitas.
- Manifesto, ícones e service worker (plataforma e vitrine, com o `basePath`).
- Cache das telas e das leituras da API para uso sem conexão, com faixa de aviso.
- Testes ponta a ponta em tela de celular, com axe, e verificação de rolagem lateral em todas as páginas do menu.

**Fora do escopo:** notificações push com o navegador fechado (exigem servidor de push e contas);
lojas de aplicativos.

## User stories
- **US-130** Como morador, abro a plataforma no celular e vejo o conteúdo da página logo no topo, com o menu a um toque.
- **US-131** Como morador, instalo a plataforma na tela inicial e ela abre como um aplicativo.
- **US-132** Como morador sem sinal, abro a plataforma e vejo os últimos alertas e dados que já tinha visto, sabendo que podem estar desatualizados.

## Requisitos funcionais
- **FR-200 Menu recolhível.** Abaixo de 768 px, o menu vira uma barra com o nome da plataforma, o contador de alertas oficiais e o botão "Menu" (`aria-expanded`, `aria-controls`). O menu abre sobre o conteúdo, fecha ao escolher uma página, com Esc e ao tocar fora, e devolve o foco ao botão. Acima de 768 px nada muda.
- **FR-201 Sem rolagem lateral.** Nenhuma página do menu tem largura maior que a tela em 360 px; tabelas largas rolam dentro do próprio quadro.
- **FR-202 Manifesto.** `manifest.webmanifest` com nome, nome curto, cores, `display: standalone`, `start_url` e `scope` com o `basePath`, ícones 192, 512 e maskable.
- **FR-203 Service worker.** Só em builds de produção. Telas e arquivos estáticos: cache e atualização em segundo plano. Leituras GET da API (e os arquivos da vitrine): rede primeiro, com até 8 s; sem rede, a última resposta guardada. Escritas nunca vão para o cache. Versão no nome do cache; versões antigas são apagadas ao ativar.
- **FR-204 Aviso sem conexão.** Sem conexão, uma faixa fixa diz "Sem conexão: você está vendo os últimos dados salvos neste aparelho. Os horários de cada dado continuam valendo." Some quando a conexão volta, e as consultas são refeitas.
- **FR-205 Telas de celular no E2E.** Projeto Playwright com tela de celular: menu recolhível (abrir, navegar, Esc), axe e verificação de rolagem lateral em todas as páginas do menu.

## Requisitos não funcionais
- **NFR-200** Cache da API limitado a 300 respostas (as mais antigas saem primeiro).
- **NFR-201** Área de toque dos itens do menu com pelo menos 44 × 44 px no celular.

## Regras de negócio
- **BR-200** Dado guardado sem conexão nunca aparece como atual: a faixa de FR-204 e os horários de cada dado ficam visíveis. Alertas oficiais guardados continuam mostrando o período de vigência original.

## Critérios de aceite
- **AC-200** *Given* uma tela de 390 px, *When* abro qualquer página do menu, *Then* o título da página aparece sem rolar e não há rolagem lateral.
- **AC-201** *Given* o menu aberto no celular, *When* aperto Esc, *Then* ele fecha e o foco volta ao botão "Menu".
- **AC-202** *Given* o build de produção, *Then* o manifesto e o service worker são servidos e o navegador oferece instalar.
- **AC-203** *Given* uma página já visitada, *When* fico sem conexão e recarrego, *Then* a página abre com os dados guardados e a faixa de FR-204.
- **AC-204** O E2E de celular passa no CI, com axe sem violações graves.

## Riscos e limitações
- O iOS só oferece instalar pelo menu Compartilhar do Safari.
- Sem conexão, só aparece o que já foi visto naquele aparelho.
