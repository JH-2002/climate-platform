# DECISIONS — Registro de decisões

Índice das ADRs em `docs/architecture/adr/`. Status possíveis: Proposta, Aceita, Substituída, Rejeitada.

| ADR | Título | Status | Data |
|---|---|---|---|
| [ADR-001](docs/architecture/adr/ADR-001-modular-monolith.md) | Monólito modular com workers Celery | Aceita | 2026-11-19 |
| [ADR-002](docs/architecture/adr/ADR-002-pilot-region-sao-paulo.md) | Região piloto: Município de São Paulo | Aceita | 2026-11-19 |
| [ADR-003](docs/architecture/adr/ADR-003-inmet-primary-observations.md) | INMET como fonte primária de observações | Aceita | 2026-11-19 |
| [ADR-004](docs/architecture/adr/ADR-004-open-meteo-forecast.md) | Open-Meteo para previsão, rotulada como FORECAST/MODELED | Aceita | 2026-11-19 |
| [ADR-005](docs/architecture/adr/ADR-005-long-format-observations.md) | Observações em formato longo (variable/value) | Aceita | 2026-11-19 |
| [ADR-006](docs/architecture/adr/ADR-006-postgis-srid.md) | PostGIS, SRID 4326 para armazenamento, 31983 para métricas | Aceita | 2026-11-19 |
| [ADR-007](docs/architecture/adr/ADR-007-current-conditions-from-forecast.md) | "Agora" a partir da previsão horária, rotulado como estimativa | Aceita | 2026-11-19 |
| [ADR-008](docs/architecture/adr/ADR-008-locations-in-browser.md) | Locais salvos no navegador até existir autenticação | Aceita | 2026-11-19 |
| [ADR-009](docs/architecture/adr/ADR-009-maplibre-2d-3d.md) | MapLibre GL para o mapa 2D/3D (no lugar de Leaflet) | Aceita | 2026-11-19 |
| [ADR-010](docs/architecture/adr/ADR-010-geosampa-risk-matrix.md) | GeoSampa como base de suscetibilidade e motor de risco em matriz | Aceita | 2026-11-19 |

## Decisões menores (sem ADR)

| Data | Decisão | Motivo |
|---|---|---|
| 2026-11-19 | Projeto em `F:\dev\climate-platform` | Preferência do responsável por manter projetos no drive F: |
| 2026-11-19 | Todo texto legível em português; identificadores, tabelas e rotas em inglês (Constituição §9.1) | Pedido do responsável + convenção técnica |
| 2026-11-19 | Repositório Git criado na T001 (Fase 1), não na Fase 0 | Fase 0 produz apenas documentos |
| 2026-11-19 | Fase 0 aprovada; ADRs 001–006 passam a **Aceita** | Aprovação do responsável |
| 2026-11-19 | Banco exposto na porta 5433 do host | PostgreSQL nativo já instalado na 5432 |
| 2026-11-19 | Heartbeat do Celery Beat via Redis para o healthcheck do container | Beat não tem comando de ping; heartbeat prova o caminho beat → broker → worker |
| 2026-11-19 | Testes de cliente HTTP sem MSW (fetch injetável) | Menos dependências, mesma cobertura |
| 2026-11-19 | `npm audit` bloqueia o CI só para dependências de produção; auditoria completa fica informativa | Alertas restantes estão no Vitest 2.x (ferramenta de teste local, não vai para produção) |
| 2026-11-19 | Frontend chama a API pela própria origem; o Next encaminha `/api/*` para o backend (`API_INTERNAL_URL`) | Elimina dependência de CORS e de portas expostas ao navegador; o navegador integrado do app bloqueava a chamada entre portas |
| 2026-11-19 | Healthcheck do banco via TCP (`pg_isready -h 127.0.0.1`) | Na primeira subida o PostGIS usa um servidor temporário só no socket local; o backend falhava na migração |
| 2026-11-19 | `overrides` força o `postcss` atualizado também dentro do Next | Next 15 embute um `postcss` com alertas altos |
| 2026-11-19 | **Pendente:** migrar Vitest 2 → versão principal atual (5.x) e revisar Next 16, Python 3.15, Node 26 | Atualizações principais exigem teste dedicado; Dependabot ignora majors até lá |
