# CURRENT STATUS

> Atualizado em: 2026-11-20

## Fase atual
- **Fase 1 — Foundation: concluída.**
- **Fase 2 — Data Ingestion: concluída**, exceto o adaptador de observações horárias do INMET (T020), que aguarda o token.
- **Fase 3 — Weather Dashboard: concluída** com previsão de modelo; medições das estações entram com o token.
- **Fase 4 — Mapa geoespacial: concluída** (MapLibre 2D/3D com relevo, estações, chuva prevista em 24 h, locais e região de interesse).
- **Fase 5 — Motor de risco de alagamento v0: concluída** (setores de risco do GeoSampa × chuva prevista, matriz explicável, ADR-010). Estimativa experimental, não alerta oficial.
- **Fase 6 — Analytics: concluída** (painel executivo na Visão geral; abas Chuva, Tendências 1933–2025, Risco, Fontes e dados e Studio; Explorador de dados; séries de referência IAG/USP e reanálise ERA5, ADR-011).

## Repositório
- GitHub: https://github.com/JH-2002/climate-platform (público), branch `main`, CI verde.
- Cópia local: `F:\dev\climate-platform`, com `origin` apontando para o GitHub.

## Em funcionamento (verificado no Docker local)
- 6 serviços `healthy`; página http://localhost:3000/status com componentes e saúde das fontes.
- Painel http://localhost:3000/weather: estimativa para agora (rotulada como modelo), gráfico de 48 h, 7 dias, chuva prevista acumulada, estações próximas e locais salvos no navegador.
- Mapa http://localhost:3000/map: 3D com relevo (padrão) ou 2D plano, camadas ligáveis, popups, legenda e lista acessível; estado do mapa guardado na URL.
- Risco http://localhost:3000/risk: resumo por categoria, filtros, ranking dos 793 setores e explicação dos fatores; camadas de setores e ocorrências no mapa; cartão no painel do clima.
- Análises http://localhost:3000/analytics e explorador http://localhost:3000/analytics/datasets: séries, climatologia, distribuição, tendências, histórico do risco, saúde das fontes e exportação CSV; KPIs e insights por regra na Visão geral http://localhost:3000.
- Coleta automática: cadastro de estações do INMET e camadas do GeoSampa (a cada 24 h) e previsão da Open-Meteo em 12 pontos (a cada 1 h, seguida do cálculo do risco), reanálise diária desde 1991 (atualização a cada 24 h) e tabela do IAG/USP (semanal), com uma coleta inicial ao iniciar o agendador.
- API: `/api/v1/health`, `/health/ready`, `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations`, `/weather/forecast`, `/map/region`, `/map/layers/stations`, `/map/layers/forecast-points`, `/map/layers/risk`, `/map/layers/flood-occurrences`, `/risk/summary`, `/risk/areas`, `/risk/areas/{id}`, `/risk/nearest`, `/analytics/*` (datasets, describe, kpis, insights, series, series.csv, climatology, distribution, ranking, trends, risk-history, sources-health) (documentação em http://localhost:8000/api/docs).

## Bloqueios externos
- **Token do INMET**: e-mail enviado em 2026-11-19 para cadastro.act@inmet.gov.br. Quando chegar: colocar em `INMET_TOKEN` no `.env` e implementar a T020 com uma resposta real gravada.

## Pendências técnicas
- Migrar Vitest 2 → versão principal atual (alertas restritos à ferramenta de teste).
- Avaliar Next 16, Python 3.15, Node 26 e as actions em versões principais novas (PR #20 do Dependabot).
- mypy fixo em 1.13 (o PR #23 do Dependabot propõe atualizar).

## Limpeza pendente no GitHub
- Branches temporários `feat/fase-3`, `feat/fase-4`, `feat/fase-5` e `chore/lockfiles` (o proxy desta sessão não permite apagar branches; podem ser removidos pela interface do GitHub).

## Próxima tarefa
Escrever a spec 007 (Simulation Lab: motor com seed, modos SIMULATION/HYBRID) para aprovação. Melhorias em aberto: calibrar as faixas de chuva do risco com ocorrências de anos anteriores; usar observações do INMET quando o token chegar; nomes das subprefeituras vêm sem acento do GeoSampa (avaliar tabela de nomes oficiais).
