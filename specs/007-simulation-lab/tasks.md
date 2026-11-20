# Tasks 007 — Laboratório de simulação

Legenda: `[ ]` pendente · `[x]` validada.

## Parte A — cenários determinísticos

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T100 | Cenário, faixas e presets | `simulation/scenario.py` | FR-100, FR-103, BR-104 | unitários | [x] |
| T101 | Chuva por setor (hietograma e fator espacial) | `simulation/rain.py` | FR-101 | unitários | [x] |
| T102 | Motor de simulação sobre o motor de risco + contrato do import-linter | `simulation/engine.py`, `pyproject.toml` | FR-102, NFR-100, AC-100, AC-101 | unitários | [x] |
| T103 | Migration `0005_simulation` | `migrations/`, `models/tables.py` | upgrade/downgrade no CI | integração | [x] |
| T104 | Serviço: setores com ponto interno, execução, gravação, comparação com o real | `services/simulation.py` | FR-104, FR-106, BR-101, BR-102 | integração | [x] |
| T105 | API e camada do mapa | `api/v1/simulation.py`, `api/v1/maps.py` | FR-105, AC-103, AC-106 | integração | [x] |
| T106 | Página `/simulation`: formulário, presets, mapa, resultados, faixa | `app/simulation/`, `components/simulation/` | FR-107, BR-100, AC-102, AC-107 | `simulation.test.tsx` | [x] |
| T107 | Validação da Parte A no navegador e documentação | docs | Navegador + CI | manual | [x] |

Validação da Parte A (2026-11-20), com os 793 setores reais:
- os 4 cenários prontos executam em ~0,2 s, e as categorias seguem a matriz do motor (40 mm em 1 h → alto nos setores de suscetibilidade 3–4; 80 mm em 24 h → 456 setores em alto);
- a célula move com clique no mapa ou por subprefeitura, e o mapa enquadra a área atingida;
- a explicação por setor fala de "cenário", não de previsão;
- Risco, indicadores da Visão geral e Fontes e dados ficam iguais depois das simulações (AC-103);
- correções da validação: a página não vaza mais para a direita em telas estreitas (`min-w-0` no conteúdo e caixas de rolagem como referência dos textos só para leitores de tela), e os setores aparecem na cor da categoria na escala da cidade.

## Parte B — incerteza com seed e modo HYBRID

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T108 | Variações com seed e agregação | `simulation/ensemble.py` | FR-108, AC-104, NFR-101 | unitários | [x] |
| T109 | Modo HYBRID sobre a previsão real | `simulation/rain.py`, `services/simulation.py` | FR-109, BR-103, AC-105 | unitários + integração | [x] |
| T110 | Histórico, repetir e aviso de mudança | `api/v1/simulation.py`, `components/simulation/HistoryList.tsx` | FR-110 | integração + frontend | [x] |
| T111 | Retenção diária | `workers/tasks/simulation.py` | NFR-102 | integração | [x] |
| T112 | Validação da Parte B e documentação | docs | Navegador + CI | manual | [x] |

Validação da Parte B (2026-11-20), com os dados reais:
- 100 variações com seed 42 em 0,4 s pela API; a tabela mostra a chance de alto ou crítico por setor (ex.: Parque do Gato, Sé: alto em 97%, crítico em 9%);
- "Repetir" com o mesmo seed devolve resultado idêntico, setor por setor; com outro seed, a diferença é apontada;
- modo a partir da previsão real: × 100% reproduz o risco real (793 setores em baixo); × 300% continua em baixo porque a previsão do dia tem no máximo 2,2 mm em 1 h (6,6 mm × 3, abaixo do gatilho de 10 mm);
- histórico lista as execuções recentes com link; limpeza diária registrada no agendador;
- correção da validação: no modo a partir da previsão real, a chuva das 72 h anteriores é descrita como real, não "no cenário".
