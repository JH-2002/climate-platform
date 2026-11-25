# Tasks 011 — Hardening

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T180 | Cabeçalhos de segurança do frontend | `lib/security-headers.mjs`, `next.config.ts` | FR-170, BR-171, AC-170 | `security.test.ts` + navegador | [x] |
| T181 | Cabeçalhos e limite de corpo na API | `core/security.py` | FR-171, FR-174, AC-174 | unitários + integração | [x] |
| T182 | Limite de requisições com Redis | `core/rate_limit.py` | FR-172, FR-173, NFR-170, AC-171 a AC-173 | unitários + integração | [x] |
| T183 | Validação da configuração de produção | `core/config.py` | FR-175, AC-175 | unitários | [x] |
| T184 | Atualizações de dependências (Dependabot) | `pyproject.toml`, workflows | CI verde | CI | [x] |
| T185 | Testes ponta a ponta com Playwright no CI | `frontend/e2e/`, `.github/workflows/ci.yml` | FR-179, AC-177 | E2E | [x] |
| T186 | Imagens e pilha de produção com Caddy | `Dockerfile.prod`, `docker-compose.prod.yml`, `deploy/` | FR-176, NFR-171, NFR-173 | Docker local | [x] |
| T187 | Backup e restauração | `deploy/backup.sh`, `scripts/restore.sh` | FR-177, AC-176 | Docker local | [x] |
| T188 | Metas de desempenho medidas | `scripts/perf_check.py` | FR-180 | Docker local | [x] |
| T189 | Manual de operação e documentação | `docs/operations/RUNBOOK.md` | FR-178 | revisão | [x] |

## Validação (2026-11-25, Docker local, dados reais)
- **T180:** cabeçalhos presentes no site e na API. O navegador percorreu Visão geral, Mapa 3D com relevo e alertas, Geointeligência 3D, Análises (12 gráficos) e Laboratório sem nenhuma violação da CSP. Achado e corrigido: sem `NEXT_PUBLIC_TERRAIN_TILES_URL` no `.env`, a CSP não liberava o provedor do relevo (os padrões agora moram em `lib/map-sources.mjs`).
- **T182:** 429 em Problem Details com `Retry-After` depois de 20 pedidos pesados no minuto, enquanto as rotas leves seguiam respondendo 200.
- **T184:** PR #20 mesclado (ações na v7). PR #24 (SQLAlchemy 2.1) incorporado aqui: os agregados passaram a usar `to_int`/`to_float`.
- **T188:** 30 requisições sequenciais por rota, pelo navegador e pelo proxy do Next (portanto um pouco acima do tempo da API sozinha):

| Rota | p50 (ms) | p95 (ms) | Meta p95 |
|---|---|---|---|
| `/alerts/active` | 22 | 30 | 200 |
| `/risk/summary` | 17 | 29 | 300 |
| `/map/layers/risk` | 84 | 169 | 800 |
| `/weather/forecast` (centro) | 74 | 81 | 300 |
| `/geo/basins` | 61 | 76 | 500 |

A spec citava `/weather/current`, rota que não existe; a meta passou para `/weather/forecast`.
- **T185:** 18 testes ponta a ponta (fluxos e axe em todas as páginas do menu) com as respostas gravadas da plataforma local; verdes no CI contra o build de produção. O axe achou um problema real (WCAG 2.5.3: o nome dos botões "Por quê?" não continha o texto visível), corrigido.
- **T186 e T187** (`scripts/validar-producao.ps1`, Docker local): pilha de produção pronta em menos de 1 min depois do build; só o Caddy publica portas; HSTS, CSP sem `unsafe-eval` e demais cabeçalhos no site e na API; 793 setores, 16 fontes e 12.000 previsões carregados; backup de 5,9 MB restaurado num banco novo com as mesmas contagens. A única diferença (subprefeituras: 0 no backup, 32 no banco) veio da coleta inicial, que gravou as subprefeituras segundos depois do backup. Memória: worker 649 MB, banco 448 MB e API 210 MB, todos dentro dos limites.
- Observação: com portas diferentes de 80/443 (teste local), o redirecionamento de http aponta para a porta 443 padrão; no servidor, com 80/443, ele está correto.
- **T189:** manual de operação e script de validação revisados com a execução real.
