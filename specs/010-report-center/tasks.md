# Tasks 010 — Central de relatórios

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — geração (backend)

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T160 | Modelo de conteúdo neutro | `reports/content.py` | BR-150 | unitários | [ ] |
| T161 | Escritor de PDF com Helvetica/WinAnsi, tabelas e barras | `reports/pdf.py`, `reports/afm.py` | NFR-150 | unitários | [ ] |
| T162 | Escritores de CSV e JSON | `reports/csv_writer.py`, `reports/json_writer.py` | NFR-154, AC-155 | unitários | [ ] |
| T163 | Migration `0009_reports` | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [ ] |
| T164 | Montadores dos 5 tipos e validação | `services/reports.py` | FR-153, FR-154, BR-151 a BR-153, AC-153 | integração | [ ] |
| T165 | Pedidos, geração, limites e retenção | `services/reports.py`, `workers/tasks/reports.py` | FR-150, FR-151, FR-155, NFR-152 | integração | [ ] |
| T166 | API de relatórios | `api/v1/reports.py` | FR-152, AC-150 a AC-154 | integração | [ ] |
| T167 | Validação da Parte A com os dados reais | docs | Docker local + CI | manual | [ ] |

## Parte B — página

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T168 | Página `/reports` com formulário e lista | `app/reports/`, `components/reports/` | FR-156, AC-156 | `reports.test.tsx` | [ ] |
| T169 | Atalhos nas páginas de Risco, Alertas, Análises e Laboratório | `components/reports/ReportShortcut.tsx` | FR-156 | idem | [ ] |
| T170 | Validação da Parte B no navegador e documentação | docs | Navegador + CI | manual | [ ] |

## Traceability
| Requisito | Tarefas | Testes |
|---|---|---|
| NFR-150 | T161 | `test_report_pdf.py` |
| NFR-154, AC-155 | T162 | `test_report_writers.py` |
| FR-150 a FR-155, AC-150 a AC-154 | T163 a T166 | `test_reports.py` |
| FR-156, AC-156 | T168, T169 | `reports.test.tsx` |
