# Tasks 009 — Alertas

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — fontes oficiais, regras e API

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T140 | Migration `0008_alerts` e 3 fontes novas | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [x] |
| T141 | Parse CAP 1.2 com guarda contra DOCTYPE/ENTITY | `integrations/cap.py` | NFR-140 | unitários | [x] |
| T142 | Feed da IDAP em fluxo, com filtro por retângulo | `integrations/idap/feed.py` | FR-140, NFR-141 | unitários | [x] |
| T143 | Avisos do INMET (RSS + CAP, municípios, cor) | `integrations/inmet/warnings.py` | FR-141, BR-142 | unitários | [x] |
| T144 | Subprefeituras do GeoSampa e limite do município | `integrations/geosampa/admin.py`, `ingestion/alert_jobs.py` | FR-142 | unitários + integração | [x] |
| T145 | Jobs de alertas com interseção, `Update`/`Cancel` e idempotência | `ingestion/alert_jobs.py`, `ingestion/runner.py` | FR-140, FR-141, AC-140 a AC-142 | integração | [x] |
| T146 | Regras do sistema (puras) e avaliação com histerese | `alerts/rules.py`, `services/alerts.py` | FR-144, NFR-143, AC-143, AC-144, AC-147 | unitários + integração | [x] |
| T147 | API de alertas e camada do mapa | `api/v1/alerts.py`, `api/v1/maps.py` | FR-143, FR-145, NFR-142 | integração | [x] |
| T148 | Tarefas e agenda (IDAP 10 min, INMET 30 min, regras 10 min e após o risco) | `workers/` | FR-144 | unitários | [x] |
| T149 | Validação da Parte A com as fontes reais e documentação | docs | Docker local + CI | manual | [x] |

## Parte B — interface e notificações

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T150 | Página `/alerts` com categorias, mapa e histórico | `app/alerts/`, `components/alerts/` | FR-146, BR-140, BR-141, BR-144 | `alerts.test.tsx` | [x] |
| T151 | Faixa global e contador no menu | `components/alerts/AlertBanner.tsx`, layout | FR-147, NFR-144, AC-145 | idem | [x] |
| T152 | Cartão "Alertas agora" e camada no Mapa | `components/alerts/`, `components/map/` | FR-148 | idem | [x] |
| T153 | Notificações neste navegador | `features/alerts/notifications.ts`, `NotificationSettings.tsx` | FR-149, AC-146 | idem | [x] |
| T154 | Validação da Parte B no navegador e documentação | docs | Navegador + CI | manual | [x] |

## Validação (2026-11-24, Docker local com as fontes reais + navegador)
- Primeira coleta: 32 subprefeituras; IDAP e INMET com sucesso. 21 alertas guardados na semana (Defesa Civil de SP e INMET), 10 vigentes ou próximos: 4 da Defesa Civil (um "Severa", cobrindo 29 subprefeituras e 89% da cidade) e 6 avisos do INMET (amarelo e laranja, até 27/11).
- Página `/alerts`: categorias separadas, texto oficial, orientação da fonte, subprefeituras atingidas, mapa, fontes "Atualizado" e histórico de 7 dias. Faixa no topo de todas as páginas e contador 6 no menu; cartão na Visão geral; camada no Mapa.
- Camada do mapa com 10 polígonos em 151 KB (limite de 1 MB).
- Ajustes da validação: selo de situação próprio (o ✕ genérico lia como "cancelado"), "as 32 subprefeituras (81% da cidade)" em vez de "toda a cidade" quando a área não cobre tudo, INMET desenhado por baixo da Defesa Civil e zoom do mapa da página só com Ctrl + roda.
- O painel do navegador usado na validação bloqueia notificações; o fluxo de permissão e o aviso único (AC-146) ficam cobertos pelos testes com a API simulada.

## Traceability
| Requisito | Tarefas | Testes |
|---|---|---|
| FR-140, NFR-141 | T142, T145 | `test_idap_feed.py`, `test_alerts.py` |
| FR-141, BR-142 | T143, T145 | `test_inmet_warnings.py`, `test_alerts.py` |
| FR-142 | T144 | `test_geosampa_admin.py`, `test_alerts.py` |
| FR-143, FR-145 | T147 | `test_alerts.py` |
| FR-144, BR-143 | T146 | `test_alert_rules.py`, `test_alerts.py` |
| FR-146 a FR-149 | T150 a T153 | `alerts.test.tsx` |
