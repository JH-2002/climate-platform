# Spec 011 — Hardening

> Status: **Em andamento** (2026-11-25) · Fase: 11 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md) · ADR: [ADR-016](../../docs/architecture/adr/ADR-016-production-stack.md)

## Contexto
As Fases 0 a 10 entregaram a plataforma funcionando localmente, no Docker de desenvolvimento:
recarga automática, banco e Redis expostos na máquina, imagem de desenvolvimento do Next, sem
limites de requisição nem cabeçalhos de segurança. A Fase 11 prepara a plataforma para ficar
pública: segurança, robustez, desempenho, acessibilidade verificada de ponta a ponta,
pilha de produção e operação (backup, atualização, recuperação).

**Hospedagem** é a dependência externa da fase. Até o usuário escolher, a pilha de produção é
preparada para **qualquer servidor Linux com Docker** e um domínio apontado para ele; a
publicação de fato fica para quando houver o servidor (ver "Fora do escopo").

## Objetivo
Uma pilha de produção que sobe com um comando, com HTTPS automático, sem portas internas
expostas, com limites contra abuso, cabeçalhos de segurança, backup diário com restauração
testada, testes ponta a ponta no CI e metas de desempenho medidas.

## Escopo
**Parte A — aplicação**
- Cabeçalhos de segurança no frontend (CSP, `frame-ancestors`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`) e na API.
- Limite de requisições por cliente na API (Redis), mais estrito nas rotas pesadas.
- Limite de tamanho do corpo das requisições.
- Endurecimento da configuração de produção (validação de segredos, documentação da API, CORS).
- Dependências: atualizações pendentes do Dependabot aplicadas com o CI verde.

**Parte B — produção e operação**
- `docker-compose.prod.yml`: imagens de produção (Next `standalone`, API sem recarga e sem dependências de desenvolvimento), Caddy na frente com HTTPS automático, só as portas 80 e 443 expostas, reinício automático, verificações de saúde, limites de memória e rotação de logs.
- Backup diário do banco (`pg_dump`), 14 dias de retenção, e restauração documentada e testada.
- Manual de operação (`docs/operations/RUNBOOK.md`): instalar, atualizar, voltar versão, restaurar, trocar segredos, diagnosticar.

**Parte C — qualidade**
- Testes ponta a ponta (Playwright) no CI, com a API simulada, nos fluxos principais, incluindo verificação de acessibilidade (axe) em todas as páginas.
- Metas de desempenho da API medidas por script contra a pilha local.

**Fora do escopo**
- Contratar servidor, domínio ou serviço de e-mail (decisão e custo do usuário).
- Contas de usuário, push e e-mail (spec própria, depois da publicação).
- WAF, CDN e monitoramento externo pago.

## User stories
- **US-110** Como mantenedor, quero subir a plataforma num servidor novo com um comando e HTTPS automático.
- **US-111** Como mantenedor, quero que um robô mal-comportado não derrube a API nem esgote o worker.
- **US-112** Como mantenedor, quero recuperar o banco de ontem se algo der errado hoje.
- **US-113** Como usuário de leitor de tela, quero que todas as páginas passem numa auditoria automática a cada mudança.
- **US-114** Como usuário, quero que a página carregue rápido mesmo com milhares de setores e alertas.

## Requisitos funcionais
- **FR-170 Cabeçalhos do frontend.** Todas as rotas do Next respondem com:
  - `Content-Security-Policy`: `default-src 'self'`; scripts só da própria origem (`'unsafe-eval'` só em desenvolvimento); estilos da própria origem e inline (Tailwind e MapLibre); imagens e conexões da própria origem e do provedor de mapas configurado; `worker-src 'self' blob:`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`; `frame-ancestors 'none'`.
  - `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`.
  - `Permissions-Policy: geolocation=(self), camera=(), microphone=(), payment=(), usb=()`.
  - `Strict-Transport-Security` é responsabilidade do Caddy, só em HTTPS.
- **FR-171 Cabeçalhos da API.** Toda resposta da API leva `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` e `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (a documentação interativa `/api/docs` é exceção, com a política que ela precisa).
- **FR-172 Limite de requisições.** Janela fixa de 1 minuto por cliente, no Redis:
  - geral: 240 requisições por minuto;
  - pesadas (`POST /simulation/runs`, `POST /reports`, `/geo/profile`, `/analytics/series`, `/analytics/describe`): 20 por minuto;
  - acima do limite: 429 (Problem Details em português) com `Retry-After`;
  - cabeçalhos `RateLimit-Limit` e `RateLimit-Remaining` nas respostas;
  - `/api/v1/health` e `/api/v1/ready` ficam fora;
  - Redis fora do ar: a requisição passa (falha aberta) e o evento é registrado no log, porque disponibilidade vale mais que o limite.
- **FR-173 IP do cliente.** O IP vem da conexão; `X-Forwarded-For` só é aceito quando a conexão chega de um proxy confiável (`TRUSTED_PROXIES`, CIDRs; por padrão as redes privadas do Docker). O IP nunca vai inteiro para o log (Constituição §5): só um hash.
- **FR-174 Tamanho do corpo.** Requisições com corpo acima de 64 KB recebem 413 antes de chegar à rota.
- **FR-175 Configuração de produção.** Com `APP_ENV=production`:
  - a inicialização falha se a senha do banco tiver menos de 16 caracteres ou for um valor de exemplo;
  - `LOG_LEVEL=DEBUG` é recusado;
  - CORS aceita só `FRONTEND_ORIGIN`, que precisa ser `https://`.
- **FR-176 Pilha de produção** (`docker-compose.prod.yml`):
  - Caddy (80/443) → frontend Next `standalone` (usuário sem privilégios) → API por dentro da rede;
  - banco e Redis sem porta publicada; Redis com senha;
  - API com 2 processos, sem `--reload`, `--proxy-headers` só da rede interna;
  - migrações rodam num serviço de uma vez (`migrate`) antes da API;
  - todos os serviços com `restart: unless-stopped`, verificação de saúde, limite de memória e logs com rotação (10 MB × 3);
  - variáveis em `.env.prod` (modelo `.env.prod.example`, sem valores reais).
- **FR-177 Backup.** Serviço `backup`: `pg_dump -Fc` diário às 03h (Brasília) num volume próprio, com o nome datado; apaga os de mais de 14 dias; registra tamanho e duração no log. `scripts/restore.sh` restaura um arquivo escolhido num banco novo e confere a contagem das tabelas principais.
- **FR-178 Manual de operação** (`docs/operations/RUNBOOK.md`): requisitos do servidor, primeira instalação, atualização, volta de versão, backup e restauração (com o teste), troca de segredos, diagnóstico pelos logs e pelas verificações de saúde, e o que fazer quando uma fonte para.
- **FR-179 Testes ponta a ponta.** Playwright contra o build de produção do Next, com a API simulada por interceptação de rede (dados gravados). Cobre:
  - Visão geral com a faixa de alerta;
  - página de Alertas;
  - Risco com filtro e detalhe;
  - Relatórios (pedido, andamento, download);
  - Laboratório (cenário pronto);
  - navegação por teclado (link "Pular para o conteúdo", menu);
  - axe sem violações graves ou críticas em todas as páginas do menu.
  
  Roda num job próprio do CI.
- **FR-180 Metas de desempenho** (`scripts/perf_check.py`, contra a pilha local com os dados reais, 50 requisições por rota). p95 de:
  - `/alerts/active` < 200 ms;
  - `/risk/summary` < 300 ms;
  - `/map/layers/risk` < 800 ms;
  - `/weather/current` < 300 ms;
  - `/geo/basins` < 500 ms.
  
  O resultado vai para o manual com a data.

## Requisitos não funcionais
- **NFR-170** O limite de requisições acrescenta no máximo 2 ms por requisição (uma ida ao Redis com pipeline).
- **NFR-171** A imagem de produção do frontend fica abaixo de 250 MB e a da API abaixo de 600 MB.
- **NFR-172** Nenhum segredo nas imagens, no repositório ou nos logs; `.env.prod` está no `.gitignore`.
- **NFR-173** A pilha de produção roda sem nenhum contêiner como root, exceto o Caddy (precisa das portas 80/443; usa a imagem oficial).

## Regras de negócio
- **BR-170** O limite de requisições nunca bloqueia a leitura de alertas oficiais por um usuário comum: 240/min por IP é muito acima do uso da tela (≈ 1 consulta a cada 2 min).
- **BR-171** A CSP não pode quebrar o mapa: o provedor de mapas configurado (`NEXT_PUBLIC_MAP_STYLE_URL`) entra em `img-src`, `connect-src` e `font-src`.

## Critérios de aceite
- **AC-170** *Given* qualquer página do frontend, *Then* a resposta tem a CSP e os demais cabeçalhos do FR-170, e o mapa, os gráficos e o relevo 3D funcionam sem erro de CSP no console.
- **AC-171** *Given* 21 requisições de `POST /reports` em menos de 1 minuto do mesmo IP, *Then* a 21ª recebe 429 com `Retry-After` e mensagem em português; outro IP continua sendo atendido.
- **AC-172** *Given* o Redis fora do ar, *Then* a API continua respondendo (sem limite) e registra o aviso.
- **AC-173** *Given* `X-Forwarded-For` vindo de um IP que não é proxy confiável, *Then* o cabeçalho é ignorado.
- **AC-174** *Given* um corpo de 100 KB, *Then* 413.
- **AC-175** *Given* `APP_ENV=production` com a senha de exemplo, *Then* a API não inicia e diz por quê.
- **AC-176** *Given* a pilha de produção, *When* faço backup e restauro num banco novo, *Then* as contagens de setores, alertas e previsões batem.
- **AC-177** *Given* o CI, *Then* o job de testes ponta a ponta passa, com axe sem violações graves em todas as páginas do menu.

## Dependências
- Specs 001 a 010.
- Hospedagem: servidor Linux com Docker e um domínio (decisão do usuário) para a publicação.
- Novas dependências: nenhuma no backend; Playwright só no job de CI (instalado ali, fora do `package.json` da aplicação).

## Riscos e limitações
- **CSP com `'unsafe-inline'` em scripts.** O Next 15 injeta scripts inline; a alternativa (nonce por requisição) desliga o cache estático das páginas. Aceito por ora: não há conteúdo de usuário renderizado como HTML, e `object-src`, `base-uri` e `frame-ancestors` ficam fechados.
- **Limite por IP.** Usuários atrás do mesmo NAT (escolas, empresas) dividem o limite; 240/min deixa folga larga.
- **Backup no mesmo servidor.** Protege de erro humano, não de perda do servidor. O manual descreve a cópia para fora (por exemplo, `rclone` para um armazenamento de objetos) como passo recomendado.
