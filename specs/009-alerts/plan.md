# Plan 009 — Alertas

## Decisões
- **Duas tabelas, duas naturezas** ([ADR-014](../../docs/architecture/adr/ADR-014-official-alerts-and-rules.md)). `official_alerts` guarda o que a fonte disse, sem reescrever. `system_alerts` guarda o que as regras do sistema concluíram. Elas nunca se misturam no banco, e a API devolve as duas com a categoria explícita (BR-140).
- **XML com a biblioteca padrão.** `xml.etree.ElementTree.iterparse` lê o feed da IDAP alerta por alerta. Antes de qualquer parse, o adapter recusa `<!DOCTYPE` e `<!ENTITY` no conteúdo: sem eles, não há expansão de entidades nem referência externa. Não entra `defusedxml` nem `lxml`.
- **Filtro espacial em duas etapas.** O adapter compara o retângulo de cada polígono com o retângulo da região e descarta o resto sem montar geometria (NFR-141). O banco faz a interseção exata com o limite do município (`ST_Intersects`) e calcula as subprefeituras atingidas e a fração de área.
- **INMET: o CAP de cada aviso.** O RSS não traz o polígono nem a lista de municípios. O job busca o CAP só dos avisos ainda não guardados (cerca de 5 por coleta depois da primeira). Avisos de outras regiões ficam numa lista de ignorados por identificador, para não serem baixados de novo.
- **Regras puras.** `app/alerts/rules.py` recebe um retrato do estado (setores por subprefeitura, frescor das fontes, idade do último risco) e os alertas abertos, e devolve as ações (abrir, atualizar, contar ausência, encerrar). O serviço aplica as ações no banco. A histerese (duas avaliações) fica no contador `clear_count`.
- **Notificações no navegador.** A API de Notificações do navegador, com permissão pedida por um botão, e consulta periódica com o TanStack Query. Sem service worker nem push: não há contas nem servidor de envio.

## Modelo de dados (migration `0008_alerts`)
| Tabela | Campos principais |
|---|---|
| `subprefectures` | `id` · `source_id` · `source_code` · `name` · `acronym` · `region5` · `geom` (MultiPolygon 4326) · `active` · `last_seen_at` · `raw_payload_id` |
| `official_alerts` | `id` · `source_id` · `category` (CIVIL_DEFENSE/WEATHER_WARNING) · `external_id` · `sender_name` · `msg_type` · `references` · `event` · `severity` · `urgency` · `certainty` · `headline` · `description` · `instruction` · `web` · `area_desc` · `color` · `sent_at` · `onset_at` · `expires_at` · `ended_at` · `ended_reason` (CANCELLED/SUPERSEDED) · `geom` (MultiPolygon simplificado) · `area_approximate` · `city_fraction` · `subprefectures` (text[]) · `raw_payload_id` · `first_seen_at` · `last_seen_at` |
| `ignored_alert_ids` | `source_id` · `external_id` · `seen_at` (avisos fora da região; limpos após 30 dias) |
| `system_alerts` | `id` · `rule_code` · `rules_version` · `scope_key` · `scope_label` · `category` (RISK_ESTIMATE/DATA_QUALITY) · `level` · `title` · `message` · `details` (JSONB) · `opened_at` · `updated_at` · `closed_at` · `clear_count` |

Índice único parcial em `system_alerts (rule_code, scope_key) WHERE closed_at IS NULL`. Mais 3 fontes em `data_sources`: `idap-alerts` (600 s), `inmet-warnings` (1.800 s) e `geosampa-subprefectures` (86.400 s).

## Backend
| Arquivo | Conteúdo |
|---|---|
| `integrations/cap.py` | Puro: parse de uma mensagem CAP 1.2 (`CapAlert`, `CapArea`), polígono CAP → GeoJSON, guarda contra DOCTYPE/ENTITY |
| `integrations/idap/feed.py` | Puro: leitura em fluxo do feed Atom, filtro por retângulo ou código IBGE |
| `integrations/inmet/warnings.py` | Puro: itens do RSS, municípios do parâmetro `Municipios`, cor e nome da severidade |
| `integrations/geosampa/admin.py` | Puro: parse das subprefeituras |
| `ingestion/alert_jobs.py` | Jobs da IDAP, do INMET e das subprefeituras; gravação com interseção no banco; `Update`/`Cancel` |
| `alerts/rules.py` | Puro: regras, versão, ações |
| `services/alerts.py` | Avaliação das regras, consultas da API, camada do mapa |
| `api/v1/alerts.py` + `maps.py` | Rotas do FR-145 |
| `workers/tasks/alerts.py` | `alerts.fetch_idap` (10 min), `alerts.fetch_inmet` (30 min), `alerts.evaluate` (10 min e após o risco) |

## Frontend
- `features/alerts/{types,api,hooks,labels,notifications}.ts`.
- `components/alerts/`: `AlertBanner` (no layout), `OfficialAlertCard`, `SystemAlertCard`, `AlertSourceStatus`, `AlertsMap`, `AlertHistory`, `NotificationSettings`, `AlertsNowCard` (Visão geral e Clima).
- `app/alerts/page.tsx`. O registro de navegação ganha `/alerts` (fase 9), com o contador.
- Camada `alerts` no `MapView` da Fase 4.

## Testes
- Unitários:
  - parse CAP da IDAP e do INMET com mensagens reais gravadas;
  - recusa de DOCTYPE;
  - filtro por retângulo;
  - `Municipios` → códigos;
  - regras (abrir, atualizar, histerese, escopo).
- Integração:
  - AC-140 a AC-144 com fixtures gravadas e banco real;
  - rotas da API;
  - camada do mapa.
- Frontend:
  - página com categorias separadas e estados (axe);
  - faixa (anúncio único);
  - notificações com a API do navegador simulada (AC-146).

## Ordem
1. Parte A: migration → adapters → jobs → regras → API → validação com as fontes reais.
2. Parte B: página → faixa e contador → cartões e camada → notificações → validação no navegador.
