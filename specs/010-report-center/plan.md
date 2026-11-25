# Plan 010 — Central de relatórios

## Decisões
- **PDF próprio, sem dependência** ([ADR-015](../../docs/architecture/adr/ADR-015-report-center.md)). `app/reports/pdf.py` escreve PDF 1.4 com as 14 fontes padrão (Helvetica e Helvetica-Bold), codificação WinAnsi (cp1252: todos os acentos do português) e as larguras das métricas AFM da Adobe, gravadas numa tabela no código. Faz quebra de linha, tabelas com quebra de página e repetição do cabeçalho, gráfico de barras e rodapé em todas as páginas. Conteúdo comprimido com zlib.
- **Conteúdo separado do formato.** `app/reports/content.py` define um `Report` neutro (título, metadados, blocos: parágrafos, números, tabelas, gráficos). Os montadores (`app/services/reports.py`) preenchem o `Report` com os serviços existentes; os escritores (`pdf.py`, `csv_writer.py`, JSON) só traduzem o `Report`. Assim, os três formatos têm sempre o mesmo conteúdo (BR-150).
- **Arquivo no banco.** Tabela `report_files` com `bytea` (NFR-151), separada da tabela de pedidos para a listagem não carregar os bytes.
- **Fila.** O pedido é gravado e a tarefa `reports.generate` é enviada ao Celery. A tarefa marca `RUNNING`, gera e grava; qualquer erro vira `FAILED` com a mensagem. Uma tarefa periódica marca como `FAILED` os pedidos presos e apaga os arquivos vencidos.
- **Sem contas.** A página guarda no navegador os ids dos pedidos feitos ali (até 50) e lista com `GET /reports?ids=`.

## Modelo de dados (migration `0009_reports`)
| Tabela | Campos principais |
|---|---|
| `report_requests` | `id` (uuid) · `report_type` · `format` · `params` (JSONB) · `title` · `mode` (REAL/SIMULATION) · `status` (QUEUED/RUNNING/DONE/FAILED/EXPIRED) · `error` · `created_at` · `started_at` · `finished_at` · `expires_at` · `bytes` · `sha256` · `filename` · `media_type` |
| `report_files` | `request_id` (PK, FK com cascade) · `content` (bytea) |

Mais uma fonte em `data_sources`? Não: relatório não é fonte de dado. O estado das gerações aparece em `/reports`.

## Backend
| Arquivo | Conteúdo |
|---|---|
| `reports/content.py` | Puro: `Report`, `Block` (texto, números, tabela, barras), `Column` com tipo e formato |
| `reports/pdf.py` + `reports/afm.py` | Puro: escritor de PDF e larguras da Helvetica |
| `reports/csv_writer.py` | Puro: CSV com BOM, `;`, vírgula decimal, comentários e escape de fórmulas |
| `reports/json_writer.py` | Puro: JSON com `metadata` |
| `services/reports.py` | Validação dos parâmetros, montadores dos 5 tipos, pedidos, geração, limpeza |
| `api/v1/reports.py` | Rotas do FR-150 e FR-152 |
| `workers/tasks/reports.py` | `reports.generate`, `reports.housekeeping` (diária e a cada 10 min para os presos) |

## Frontend
- `features/reports/{types,api,hooks,storage,params}.ts`.
- `components/reports/`: `ReportForm` (tipo, formato, parâmetros), `ReportList` (andamento, download), `ReportShortcut` (link "Gerar relatório").
- `app/reports/page.tsx`; o registro de navegação marca `/reports` como implementado.
- Atalhos nas páginas de Risco, Alertas, Análises e Laboratório.

## Testes
- Unitários: PDF (estrutura, xref, páginas, texto em WinAnsi, quebra de página das tabelas), CSV (BOM, separador, decimal, escape), JSON, validação dos parâmetros.
- Integração: AC-150 a AC-155 com o banco e os dados das fixtures (geração chamada direto, sem Celery); limites (429).
- Frontend: formulário (parâmetros por tipo), lista com andamento e download, armazenamento dos ids, axe.

## Ordem
1. Parte A: conteúdo e escritores (puros) → migration → montadores → API e tarefas → validação com os dados reais.
2. Parte B: página e atalhos → validação no navegador.
