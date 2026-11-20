# Tasks 007 — Laboratório de simulação

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — cenários determinísticos

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T100 | Cenário, faixas e presets | `simulation/scenario.py` | FR-100, FR-103, BR-104 | unitários | [ ] |
| T101 | Chuva por setor (hietograma e fator espacial) | `simulation/rain.py` | FR-101 | unitários | [ ] |
| T102 | Motor de simulação sobre o motor de risco + contrato do import-linter | `simulation/engine.py`, `pyproject.toml` | FR-102, NFR-100, AC-100, AC-101 | unitários | [ ] |
| T103 | Migration `0005_simulation` | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [ ] |
| T104 | Serviço: setores com ponto interno, execução, gravação, comparação com o real | `services/simulation.py` | FR-104, FR-106, BR-101, BR-102 | integração | [ ] |
| T105 | API e camada do mapa | `api/v1/simulation.py`, `api/v1/maps.py` | FR-105, AC-103, AC-106 | integração | [ ] |
| T106 | Página `/simulation`: formulário, presets, mapa, resultados, faixa | `app/simulation/`, `components/simulation/` | FR-107, BR-100, AC-102, AC-107 | `simulation.test.tsx` | [ ] |
| T107 | Validação da Parte A no navegador e documentação | docs | Navegador + CI | manual | [ ] |

## Parte B — incerteza com seed e modo HYBRID

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T108 | Variações com seed e agregação | `simulation/ensemble.py` | FR-108, AC-104, NFR-101 | unitários | [ ] |
| T109 | Modo HYBRID sobre a previsão real | `simulation/rain.py`, `services/simulation.py` | FR-109, BR-103, AC-105 | unitários + integração | [ ] |
| T110 | Histórico, repetir e aviso de mudança | `api/v1/simulation.py`, `components/simulation/HistoryList.tsx` | FR-110 | integração + frontend | [ ] |
| T111 | Retenção diária | `workers/tasks/simulation.py` | NFR-102 | integração | [ ] |
| T112 | Validação da Parte B e documentação | docs | Navegador + CI | manual | [ ] |
