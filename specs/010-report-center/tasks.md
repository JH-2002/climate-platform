# Tasks 010 — Central de relatórios

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — geração (backend)

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T160 | Modelo de conteúdo neutro | `reports/content.py` | BR-150 | unitários | [x] |
| T161 | Escritor de PDF com Helvetica/WinAnsi, tabelas e barras | `reports/pdf.py`, `reports/afm.py` | NFR-150 | unitários | [x] |
| T162 | Escritores de CSV e JSON | `reports/csv_writer.py`, `reports/json_writer.py` | NFR-154, AC-155 | unitários | [x] |
| T163 | Migration `0009_reports` | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [x] |
| T164 | Montadores dos 5 tipos e validação | `services/reports.py` | FR-153, FR-154, BR-151 a BR-153, AC-153 | integração | [x] |
| T165 | Pedidos, geração, limites e retenção | `services/reports.py`, `workers/tasks/reports.py` | FR-150, FR-151, FR-155, NFR-152 | integração | [x] |
| T166 | API de relatórios | `api/v1/reports.py` | FR-152, AC-150 a AC-154 | integração | [x] |
| T167 | Validação da Parte A com os dados reais | docs | Docker local + CI | manual | [x] |

## Parte B — página

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T168 | Página `/reports` com formulário e lista | `app/reports/`, `components/reports/` | FR-156, AC-156 | `reports.test.tsx` | [x] |
| T169 | Atalhos nas páginas de Risco, Alertas, Análises e Laboratório | `components/reports/ReportShortcut.tsx` | FR-156 | idem | [x] |
| T170 | Validação da Parte B no navegador e documentação | docs | Navegador + CI | manual | [x] |

## Validação (2026-11-25, Docker local com os dados reais + navegador)
- Gerados no worker, com os dados reais: Situação agora em PDF (3 páginas, 6,6 KB: 5 alertas oficiais vigentes ou próximos, risco, chuva prevista nos 12 pontos e estado das 18 fontes), Risco por setor em CSV (793 setores + 7 linhas de comentário, 203 KB), Alertas de 20 a 25/11 em PDF (4 páginas, 10 alertas da Defesa Civil e 9 avisos do INMET), Chuva de 2025 por mês em JSON (com a normal 1991–2020) e uma simulação HYBRID em PDF (21 páginas, faixa de simulação em todas).
- Página `/reports`: atalho da página de Risco abre o formulário preenchido (Penha, CSV); o pedido aparece em "Na fila", vira "Pronto" e oferece o download, e continua na lista ao recarregar.
- Ajustes da validação: coluna "Situação" mais larga no PDF (cortava "Encerrado"), valores do JSON arredondados (sem `112.00000000000001`) e horário real de término gravado pelo worker.

## Traceability
| Requisito | Tarefas | Testes |
|---|---|---|
| NFR-150 | T161 | `test_report_pdf.py` |
| NFR-154, AC-155 | T162 | `test_report_writers.py` |
| FR-150 a FR-155, AC-150 a AC-154 | T163 a T166 | `test_reports.py` |
| FR-156, AC-156 | T168, T169 | `reports.test.tsx` |
