# CURRENT STATUS

> Atualizado em: 2026-11-25

## Fase atual
- **Fase 1 — Foundation: concluída.**
- **Fase 2 — Data Ingestion: concluída**, exceto o adaptador de observações horárias do INMET (T020), que aguarda o token.
- **Fase 3 — Weather Dashboard: concluída** com previsão de modelo; medições das estações entram com o token.
- **Fase 4 — Mapa geoespacial: concluída** (MapLibre 2D/3D com relevo, estações, chuva prevista em 24 h, locais e região de interesse).
- **Fase 5 — Motor de risco de alagamento v0: concluída** (setores de risco do GeoSampa × chuva prevista, matriz explicável, ADR-010). Estimativa experimental, não alerta oficial.
- **Fase 6 — Analytics: concluída** (painel executivo na Visão geral; abas Chuva, Tendências 1933–2025, Risco, Fontes e dados e Studio; Explorador de dados; séries de referência IAG/USP e reanálise ERA5, ADR-011).
- **Fase 7 — Laboratório de simulação: concluída** (cenários sobre o motor de risco na resolução de setor, variações com seed, modo a partir da previsão real, histórico e repetição verificada; ADR-012).
- **Fase 8 — Geointeligência 3D: concluída** (bacias, drenagem e piscinões do GeoSampa; Copernicus DEM; terreno por setor e bacia; perfil; bloco 3D da bacia no MapLibre sobre o relevo do Copernicus, com simulação, exportação PNG e versão 2D; ADR-013).
- **Fase 9 — Alertas: concluída** (alertas da Defesa Civil pelo feed CAP da IDAP, avisos do INMET, limite pelas subprefeituras do GeoSampa, alertas do sistema por regras com histerese, página `/alerts`, faixa global, cartões, camada no mapa e notificações neste navegador; ADR-014).
- **Fase 10 — Central de relatórios: concluída** (situação agora, risco por setor, alertas do período, chuva do período e simulação, em PDF, CSV e JSON, gerados no worker; PDF próprio sem dependência nova; arquivos por 7 dias; ADR-015).
- **Fase 11 — Hardening: concluída** (limite de requisições, cabeçalhos de segurança e CSP, validação da configuração de produção, testes ponta a ponta com Playwright e axe no CI, pilha de produção com Caddy e HTTPS, backup diário com restauração conferida, metas de desempenho medidas e manual de operação; ADR-016).
- **Fase 12 — Vitrine pública: concluída** — https://jh-2002.github.io/climate-platform/ (GitHub Pages, dados reais coletados e gravados pelo Actions a cada 6 h e a cada mudança no código; ADR-017).
- **Fase 13 — Celular e app instalável: concluída** (menu recolhível, PWA com ícones próprios e service worker, uso sem conexão com aviso, tabelas roláveis acessíveis pelo teclado, E2E em tela de celular).
- **Fase 14 — Atualização das dependências: concluída** (Vitest 5, jsdom 31, Recharts 3, Next 16, mypy 2.4, ruff 0.17; spec 014).
- **Publicação completa:** a pilha de produção está pronta e validada na máquina local; falta escolher a hospedagem (servidor Linux com Docker e um domínio).

## Repositório
- GitHub: https://github.com/JH-2002/climate-platform (público), branch `main`, CI verde.
- Cópia local: `F:\dev\climate-platform`, com `origin` apontando para o GitHub.

## Em funcionamento (verificado no Docker local)
- 6 serviços `healthy`; página http://localhost:3000/status com componentes e saúde das fontes.
- Painel http://localhost:3000/weather: estimativa para agora (rotulada como modelo), gráfico de 48 h, 7 dias, chuva prevista acumulada, estações próximas e locais salvos no navegador.
- Mapa http://localhost:3000/map: 3D com relevo (padrão) ou 2D plano, camadas ligáveis, popups, legenda e lista acessível; estado do mapa guardado na URL.
- Risco http://localhost:3000/risk: resumo por categoria, filtros, ranking dos 793 setores e explicação dos fatores; camadas de setores e ocorrências no mapa; cartão no painel do clima.
- Análises http://localhost:3000/analytics e explorador http://localhost:3000/analytics/datasets: séries, climatologia, distribuição, tendências, histórico do risco, saúde das fontes e exportação CSV; KPIs e insights por regra na Visão geral http://localhost:3000.
- Laboratório de simulação http://localhost:3000/simulation: cenários prontos, célula de chuva no mapa, variações com seed (chance de alto ou crítico por setor), modo a partir da previsão real, comparação com a estimativa real, histórico e repetição, com link guardado por 30 dias.
- Alertas http://localhost:3000/alerts: Defesa Civil e INMET separados da estimativa do sistema e da qualidade dos dados, com mapa, histórico de 7 dias, faixa no topo de todas as páginas, contador no menu e notificações opcionais neste navegador.
- Relatórios http://localhost:3000/reports: PDF, CSV e JSON com fonte, tipo do dado, horário e avisos; pedidos deste navegador com andamento e download; atalhos nas páginas de Risco, Alertas, Análises e Laboratório.
- Geointeligência http://localhost:3000/geo-3d: bacias por risco atual, ficha da bacia, drenagem e piscinões no mapa 2D/3D, perfil do relevo, seção Terreno na explicação dos setores e aba Bloco 3D (bacia em relevo com setores reais ou de uma simulação, exagero vertical, exportação PNG e versão 2D com tabela).
- Coleta automática: cadastro de estações do INMET e camadas do GeoSampa (a cada 24 h) e previsão da Open-Meteo em 12 pontos (a cada 1 h, seguida do cálculo do risco), reanálise diária desde 1991 (atualização a cada 24 h) tabela do IAG/USP (semanal) limpeza das simulações com mais de 30 dias (diária), alertas da Defesa Civil (10 min), avisos do INMET (30 min), regras dos alertas do sistema (10 min e após cada risco), subprefeituras (24 h) e limpeza dos relatórios (10 min), com uma coleta inicial ao iniciar o agendador.
- API: `/api/v1/health`, `/health/ready`, `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations`, `/weather/forecast`, `/map/region`, `/map/layers/stations`, `/map/layers/forecast-points`, `/map/layers/risk`, `/map/layers/flood-occurrences`, `/risk/summary`, `/risk/areas`, `/risk/areas/{id}`, `/risk/nearest`, `/simulation/*` (presets, centers, runs, histórico), `/map/layers/simulation/{id}`, `/geo/*` (dem, basins, sectors/{id}/terrain, elevation, profile, terrain/{z}/{x}/{y}.png, basins/{id}/block, basins/{id}/relief.png), `/map/layers/basins|drainage|reservoirs`, `/alerts` (active, histórico, official/{id}, at, rules), `/map/layers/alerts`, `/reports` (types, pedido, lista, andamento, download), `/analytics/*` (datasets, describe, kpis, insights, series, series.csv, climatology, distribution, ranking, trends, risk-history, sources-health) (documentação em http://localhost:8000/api/docs).

## Bloqueios externos
- **Token do INMET**: pedido por e-mail em 2026-11-19. A resposta de 2026-11-23 não concede token: indica o portal, o BDMEP (dados históricos, pedido manual por e-mail) e, para acesso por API, um Acordo de Cooperação Técnica (ACT) entre instituições. Sem token, as observações das estações do INMET continuam indisponíveis (FR-028), e a T020 fica fora do escopo enquanto não houver ACT. Cadastro de estações, avisos meteorológicos e previsão não dependem do token.

- **Cemaden (chuva medida)**: a plataforma PED tem cadastro aberto, mas o login exige captcha; a coleta automática depende de criar a conta e confirmar se existe acesso por API sem captcha.

## Pendências técnicas
- Adiados na spec 014: ESLint 10 (plugins do eslint-config-next sem suporte declarado), Tailwind 4 (migração visual completa) e TypeScript 7 (compilador novo).
- Python 3.15 e Node 26 nas imagens: avaliar quando forem as versões de suporte longo usadas pelas dependências.

## Limpeza pendente no GitHub
- Branches temporários `feat/fase-3`, `feat/fase-4`, `feat/fase-5` e `chore/lockfiles` (o proxy desta sessão não permite apagar branches; podem ser removidos pela interface do GitHub).

## Próxima tarefa
Escolher a hospedagem e publicar seguindo `docs/operations/RUNBOOK.md`. Melhorias em aberto: estados de atenção do CGE quando houver acesso permitido; notificação com o navegador fechado e relatórios agendados (exigem contas); calibrar as faixas de chuva do risco com ocorrências de anos anteriores; LiDAR da Prefeitura para o detalhe dos setores pequenos.
