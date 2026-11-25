# Spec 012 — Vitrine pública (GitHub Pages)

> Status: **Em andamento** (2026-11-25) · Fase: 12 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md) · ADR: [ADR-017](../../docs/architecture/adr/ADR-017-public-demo-pages.md)

## Contexto
A Fase 11 deixou a pilha de produção pronta e validada, mas publicar exige um servidor ligado o
tempo todo, e o usuário não tem hospedagem agora. O GitHub Pages hospeda de graça só arquivos
estáticos: não roda a API, o worker, o banco nem o Redis.

## Objetivo
Uma vitrine pública e gratuita da plataforma, num link do GitHub Pages, com dados reais que se
atualizam sozinhos algumas vezes por dia. Um workflow do GitHub Actions sobe a plataforma
completa por alguns minutos, roda as coletas reais, percorre a interface gravando as respostas
da API e publica o frontend estático com essas respostas.

## Escopo
- Modo demonstração no frontend: as leituras da API vêm de arquivos estáticos gravados.
- Workflow agendado (a cada 6 h e sob demanda) que coleta, grava, monta e publica.
- Cenários prontos do Laboratório já simulados na gravação.
- Faixa fixa avisando que é uma demonstração, com o horário dos dados.

**Fora do escopo:** geração de relatórios e simulações com valores livres (precisam do servidor);
notificações; dados de séries longas além do que a coleta cabe no tempo do workflow.

## User stories
- **US-120** Como visitante, abro o link público e navego por todas as páginas com dados reais recentes, sem instalar nada.
- **US-121** Como visitante, entendo de imediato que é uma demonstração e de quando são os dados.
- **US-122** Como dono do projeto, a vitrine se atualiza sozinha, sem servidor e sem custo.

## Requisitos funcionais
- **FR-190 Modo demonstração.** Com `NEXT_PUBLIC_DEMO=1`, o cliente da API lê `GET /api/v1/<caminho>?<consulta>` do arquivo `demo-data/<caminho>/<chave>.json`, onde a chave vem da consulta em forma canônica (parâmetros ordenados, codificação igual nos dois lados). Sem o arquivo exato, usa a resposta gravada do caminho sem consulta, se houver; sem nenhuma, responde como erro da API: "Indisponível na demonstração pública".
- **FR-191 Escritas.** Simulação: um cenário pronto sem alteração devolve a simulação gravada daquele cenário; qualquer outro corpo responde "Na demonstração pública só os cenários prontos podem ser simulados". Relatórios: "A geração de relatórios precisa da plataforma rodando (veja o README)". O formulário continua visível.
- **FR-192 Faixa de demonstração** em todas as páginas: "Demonstração pública · dados de <data e hora> · sem servidor: relatórios e simulações livres desligados", com link para o repositório.
- **FR-193 Export estático.** `next build` com `output: "export"` e `basePath` do repositório, sem rewrites nem cabeçalhos (que o Pages não aplica). Imagens e blocos servidos pela API (relevo da bacia, terreno) apontam para os arquivos gravados.
- **FR-194 Coleta no CI.** O workflow sobe PostGIS e Redis como serviços, aplica as migrações e roda as coletas em sequência: subprefeituras, camadas do GeoSampa, estações, previsão, tabela do IAG, reanálise (pontos até o limite de tempo), relevo, Defesa Civil, INMET, risco e alertas do sistema. Uma fonte que falhar não derruba as outras; a página Estado do sistema mostra o resultado real de cada uma.
- **FR-195 Gravação.** Um roteiro Playwright (fora dos testes do CI) percorre todas as páginas do menu e as interações principais contra a plataforma no ar, grava cada resposta GET da API (JSON e imagens) e roda cada cenário pronto do Laboratório. Coleções grandes **não** são cortadas (diferente do E2E): a vitrine mostra os dados completos.
- **FR-196 Publicação.** O workflow monta o site estático com os arquivos gravados e publica no GitHub Pages. Roda a cada 6 h e manualmente (`workflow_dispatch`). Se a coleta ou a gravação falhar, a versão anterior continua no ar.

## Requisitos não funcionais
- **NFR-190** Workflow completo em até 30 min.
- **NFR-191** Site publicado com até 60 MB.
- **NFR-192** Nada de segredo no site: só respostas públicas da API; o token do INMET (se existir um dia) nunca entra no workflow da vitrine.

## Regras de negócio
- **BR-190** A vitrine nunca apresenta dado gravado como "agora" sem dizer de quando é: a faixa mostra o horário da gravação, e as telas continuam mostrando os horários dos próprios dados.
- **BR-191** As atribuições das fontes continuam em todas as telas, como na plataforma.

## Critérios de aceite
- **AC-190** *Given* o link público, *When* abro cada página do menu, *Then* ela carrega com dados e sem erro de "Indisponível" no conteúdo principal.
- **AC-191** *Given* o Laboratório, *When* clico num cenário pronto e em "Simular", *Then* vejo o resultado gravado daquele cenário.
- **AC-192** *Given* o Laboratório, *When* altero um valor e clico em "Simular", *Then* vejo a mensagem de FR-191.
- **AC-193** *Given* o workflow, *When* roda pelo agendamento, *Then* a faixa passa a mostrar o novo horário.
- **AC-194** A gravação e a leitura usam o mesmo módulo (`frontend/lib/demo.ts`) para transformar caminho, consulta e corpo em nome de arquivo; os casos ficam testados no Vitest.

## Dependências
- GitHub Pages ativado no repositório (fonte: GitHub Actions).
- Fontes públicas alcançáveis pelos executores do GitHub.

## Riscos e limitações
- Interações que pedem consultas não gravadas (um filtro raro, um ponto qualquer do perfil do relevo) mostram "Indisponível na demonstração".
- Fontes externas podem bloquear ou limitar os executores do GitHub; a vitrine mostra a fonte como indisponível, como a plataforma faria.
- A reanálise desde 1991 é coletada aos poucos; numa execução cabe só parte dos pontos.
