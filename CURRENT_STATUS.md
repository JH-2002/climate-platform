# CURRENT STATUS

> Atualizado em: 2026-11-24

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
- **Próxima: Fase 10 — Central de relatórios** (spec 010 a escrever).

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
- Geointeligência http://localhost:3000/geo-3d: bacias por risco atual, ficha da bacia, drenagem e piscinões no mapa 2D/3D, perfil do relevo, seção Terreno na explicação dos setores e aba Bloco 3D (bacia em relevo com setores reais ou de uma simulação, exagero vertical, exportação PNG e versão 2D com tabela).
- Coleta automática: cadastro de estações do INMET e camadas do GeoSampa (a cada 24 h) e previsão da Open-Meteo em 12 pontos (a cada 1 h, seguida do cálculo do risco), reanálise diária desde 1991 (atualização a cada 24 h) tabela do IAG/USP (semanal) limpeza das simulações com mais de 30 dias (diária), alertas da Defesa Civil (10 min), avisos do INMET (30 min), regras dos alertas do sistema (10 min e após cada risco) e subprefeituras (24 h), com uma coleta inicial ao iniciar o agendador.
- API: `/api/v1/health`, `/health/ready`, `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations`, `/weather/forecast`, `/map/region`, `/map/layers/stations`, `/map/layers/forecast-points`, `/map/layers/risk`, `/map/layers/flood-occurrences`, `/risk/summary`, `/risk/areas`, `/risk/areas/{id}`, `/risk/nearest`, `/simulation/*` (presets, centers, runs, histórico), `/map/layers/simulation/{id}`, `/geo/*` (dem, basins, sectors/{id}/terrain, elevation, profile, terrain/{z}/{x}/{y}.png, basins/{id}/block, basins/{id}/relief.png), `/map/layers/basins|drainage|reservoirs`, `/alerts` (active, histórico, official/{id}, at, rules), `/map/layers/alerts`, `/analytics/*` (datasets, describe, kpis, insights, series, series.csv, climatology, distribution, ranking, trends, risk-history, sources-health) (documentação em http://localhost:8000/api/docs).

## Bloqueios externos
- **Token do INMET**: e-mail enviado em 2026-11-19 para cadastro.act@inmet.gov.br. Quando chegar: colocar em `INMET_TOKEN` no `.env` e implementar a T020 com uma resposta real gravada.

## Pendências técnicas
- Migrar Vitest 2 → versão principal atual (alertas restritos à ferramenta de teste).
- Avaliar Next 16, Python 3.15, Node 26 e as actions em versões principais novas (PR #20 do Dependabot).
- mypy fixo em 1.13 (o PR #23 do Dependabot propõe atualizar).

## Limpeza pendente no GitHub
- Branches temporários `feat/fase-3`, `feat/fase-4`, `feat/fase-5` e `chore/lockfiles` (o proxy desta sessão não permite apagar branches; podem ser removidos pela interface do GitHub).

## Próxima tarefa
Fase 10 — Central de relatórios: escrever a spec 010 (PDF/CSV/JSON gerados em segundo plano). Melhorias em aberto: estados de atenção do CGE quando houver acesso permitido; notificação com o navegador fechado (exige contas, Fase 11); calibrar as faixas de chuva do risco com ocorrências de anos anteriores; reproduzir eventos passados quando houver chuva horária medida (INMET ou CEMADEN); LiDAR da Prefeitura para o detalhe dos setores pequenos.
