# Plan 012 — Vitrine pública (GitHub Pages)

## Decisões
- **Gravar a interface, não a API inteira** ([ADR-017](../../docs/architecture/adr/ADR-017-public-demo-pages.md)). Um roteiro Playwright percorre as páginas como um visitante e grava o que o frontend pede, então a vitrine tem exatamente as consultas que a interface faz (filtros padrão, recorte do mapa, séries das Análises), sem manter uma lista de rotas à mão. Rotas de detalhe (setores, bacias) são completadas pelo próprio roteiro a partir das listas gravadas.
- **Chave do arquivo igual nos dois lados.** `demo-data/<caminho>/index.json` sem consulta e `demo-data/<caminho>/q-<fnv1a>.json` com consulta; FNV-1a de 32 bits sobre a consulta canônica (pares ordenados, codificação do `encodeURIComponent`). POST de simulação: `post-<fnv1a do corpo canônico>.json`. Um módulo só (`frontend/lib/demo.ts`), usado pelo roteiro de gravação (Playwright, TypeScript) e pelo cliente da API.
- **Dados não vão para o repositório.** O workflow gera, monta e publica o artefato do Pages; o repositório só guarda o código.
- **Coleta reaproveita `app/ingestion/runner.py`** (as mesmas funções das tarefas do Celery), num script `backend/scripts/demo_collect.py` que registra o resultado de cada fonte e segue em frente quando uma falha.
- **API sem limite de requisições na gravação** (`RATE_LIMIT_ENABLED=false`): o roteiro faz centenas de consultas em poucos minutos.

## Frontend
| Arquivo | Conteúdo |
|---|---|
| `lib/demo.ts` | Chaves, URL do arquivo, regras de escrita (puro, testado) |
| `lib/api-client.ts` | No modo demonstração, GET e POST passam por `lib/demo.ts` |
| `components/layout/DemoBanner.tsx` | Faixa com o horário da gravação |
| `next.config.ts` | `output: "export"` e `basePath` quando `NEXT_PUBLIC_DEMO=1` |
| `features/geo/api.ts`, `features/analytics/api.ts` | URLs diretas (relevo, terreno, CSV) pelo helper |

## Backend e CI
| Arquivo | Conteúdo |
|---|---|
| `scripts/demo_collect.py` | Coletas em sequência, com resumo por fonte |
| `frontend/demo/record.spec.ts`, `frontend/demo/playwright.config.ts` | Roteiro de gravação |
| `.github/workflows/demo.yml` | Agendado a cada 6 h e manual: serviços, coleta, API, gravação, build estático, publicação |

## Testes
- Vitest: chaves (tabela compartilhada), leitura com e sem consulta, fallback, mensagens de escrita, faixa.
- pytest: resumo da coleta (`demo_collect`).
- O workflow da vitrine é o teste de ponta a ponta: falha se alguma página do menu ficar sem dados.

## Sequência
1. Chaves + modo demonstração no frontend. 2. Coleta e gravação. 3. Workflow e Pages. 4. Validação no link público.
