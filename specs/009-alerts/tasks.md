# Tasks 009 — Alertas

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — fontes oficiais, regras e API

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T140 | Migration `0008_alerts` e 3 fontes novas | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [ ] |
| T141 | Parse CAP 1.2 com guarda contra DOCTYPE/ENTITY | `integrations/cap.py` | NFR-140 | unitários | [ ] |
| T142 | Feed da IDAP em fluxo, com filtro por retângulo | `integrations/idap/feed.py` | FR-140, NFR-141 | unitários | [ ] |
| T143 | Avisos do INMET (RSS + CAP, municípios, cor) | `integrations/inmet/warnings.py` | FR-141, BR-142 | unitários | [ ] |
| T144 | Subprefeituras do GeoSampa e limite do município | `integrations/geosampa/admin.py`, `ingestion/alert_jobs.py` | FR-142 | unitários + integração | [ ] |
| T145 | Jobs de alertas com interseção, `Update`/`Cancel` e idempotência | `ingestion/alert_jobs.py`, `ingestion/runner.py` | FR-140, FR-141, AC-140 a AC-142 | integração | [ ] |
| T146 | Regras do sistema (puras) e avaliação com histerese | `alerts/rules.py`, `services/alerts.py` | FR-144, NFR-143, AC-143, AC-144, AC-147 | unitários + integração | [ ] |
| T147 | API de alertas e camada do mapa | `api/v1/alerts.py`, `api/v1/maps.py` | FR-143, FR-145, NFR-142 | integração | [ ] |
| T148 | Tarefas e agenda (IDAP 10 min, INMET 30 min, regras 10 min e após o risco) | `workers/` | FR-144 | unitários | [ ] |
| T149 | Validação da Parte A com as fontes reais e documentação | docs | Docker local + CI | manual | [ ] |

## Parte B — interface e notificações

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T150 | Página `/alerts` com categorias, mapa e histórico | `app/alerts/`, `components/alerts/` | FR-146, BR-140, BR-141, BR-144 | `alerts.test.tsx` | [ ] |
| T151 | Faixa global e contador no menu | `components/alerts/AlertBanner.tsx`, layout | FR-147, NFR-144, AC-145 | idem | [ ] |
| T152 | Cartão "Alertas agora" e camada no Mapa | `components/alerts/`, `components/map/` | FR-148 | idem | [ ] |
| T153 | Notificações neste navegador | `features/alerts/notifications.ts`, `NotificationSettings.tsx` | FR-149, AC-146 | idem | [ ] |
| T154 | Validação da Parte B no navegador e documentação | docs | Navegador + CI | manual | [ ] |

## Traceability
| Requisito | Tarefas | Testes |
|---|---|---|
| FR-140, NFR-141 | T142, T145 | `test_idap_feed.py`, `test_alerts.py` |
| FR-141, BR-142 | T143, T145 | `test_inmet_warnings.py`, `test_alerts.py` |
| FR-142 | T144 | `test_geosampa_admin.py`, `test_alerts.py` |
| FR-143, FR-145 | T147 | `test_alerts.py` |
| FR-144, BR-143 | T146 | `test_alert_rules.py`, `test_alerts.py` |
| FR-146 a FR-149 | T150 a T153 | `alerts.test.tsx` |
