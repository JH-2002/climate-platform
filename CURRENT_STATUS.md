# CURRENT STATUS

> Atualizado em: 2026-11-19

## Fase atual
- **Fase 1 — Foundation: concluída.**
- **Fase 2 — Data Ingestion: concluída**, exceto o adaptador de observações horárias do INMET (T020), que aguarda o token.
- **Fase 3 — Weather Dashboard: concluída** com previsão de modelo; medições das estações entram com o token.
- **Fase 4 — Mapa geoespacial: concluída** (MapLibre 2D/3D com relevo, estações, chuva prevista em 24 h, locais e região de interesse).
- Próxima: **Fase 5 — Flood Risk Engine** (spec 005 a escrever).

## Repositório
- GitHub: https://github.com/JH-2002/climate-platform (público), branch `main`, CI verde.
- Cópia local: `F:\dev\climate-platform`, com `origin` apontando para o GitHub.

## Em funcionamento (verificado no Docker local)
- 6 serviços `healthy`; página http://localhost:3000/status com componentes e saúde das fontes.
- Painel http://localhost:3000/weather: estimativa para agora (rotulada como modelo), gráfico de 48 h, 7 dias, chuva prevista acumulada, estações próximas e locais salvos no navegador.
- Mapa http://localhost:3000/map: 3D com relevo (padrão) ou 2D plano, camadas ligáveis, popups, legenda e lista acessível; estado do mapa guardado na URL.
- Coleta automática: cadastro de estações do INMET (a cada 24 h) e previsão da Open-Meteo (a cada 1 h), com uma coleta inicial ao iniciar o agendador.
- API: `/api/v1/health`, `/health/ready`, `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations`, `/weather/forecast`, `/map/region`, `/map/layers/stations`, `/map/layers/forecast-points` (documentação em http://localhost:8000/api/docs).

## Bloqueios externos
- **Token do INMET**: e-mail enviado em 2026-11-19 para cadastro.act@inmet.gov.br. Quando chegar: colocar em `INMET_TOKEN` no `.env` e implementar a T020 com uma resposta real gravada.

## Pendências técnicas
- Migrar Vitest 2 → versão principal atual (alertas restritos à ferramenta de teste).
- Avaliar Next 16, Python 3.15, Node 26 e as actions em versões principais novas (PR #20 do Dependabot).
- mypy fixo em 1.13 (o PR #23 do Dependabot propõe atualizar).

## Limpeza pendente no GitHub
- Branches temporários `feat/fase-3`, `feat/fase-4` e `chore/lockfiles` (o proxy desta sessão não permite apagar branches; podem ser removidos pela interface do GitHub).

## Próxima tarefa
Escrever a spec 005 (motor heurístico de risco de alagamento v0, experimental e explicável).
