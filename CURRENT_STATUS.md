# CURRENT STATUS

> Atualizado em: 2026-11-19

## Fase atual
- **Fase 1 — Foundation: concluída.**
- **Fase 2 — Data Ingestion: concluída**, exceto o adaptador de observações horárias do INMET (T020), que aguarda o token.
- Próxima: **Fase 3 — Weather Dashboard** (spec 003 a escrever).

## Repositório
- GitHub: https://github.com/JH-2002/climate-platform (público), branch `main`, CI verde.
- Cópia local: `F:\dev\climate-platform`, com `origin` apontando para o GitHub.

## Em funcionamento (verificado no Docker local)
- 6 serviços `healthy`; página http://localhost:3000/status com componentes e saúde das fontes.
- Coleta automática: cadastro de estações do INMET (a cada 24 h) e previsão da Open-Meteo (a cada 1 h), com uma coleta inicial ao iniciar o agendador.
- API: `/api/v1/health`, `/health/ready`, `/sources/status`, `/stations`, `/stations/nearby`, `/stations/{id}/observations` (documentação em http://localhost:8000/api/docs).

## Bloqueios externos
- **Token do INMET**: e-mail enviado em 2026-11-19 para cadastro.act@inmet.gov.br. Quando chegar: colocar em `INMET_TOKEN` no `.env` e implementar a T020 com uma resposta real gravada.

## Pendências técnicas
- Migrar Vitest 2 → versão principal atual (alertas restritos à ferramenta de teste).
- Avaliar Next 16, Python 3.15, Node 26 e as actions em versões principais novas (PR #20 do Dependabot).
- mypy fixo em 1.13 (o PR #23 do Dependabot propõe atualizar).

## Próxima tarefa
Escrever a spec 003 (dashboard meteorológico: condições atuais, previsão, acumulados de chuva, locais do usuário).
