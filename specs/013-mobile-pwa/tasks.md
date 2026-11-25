# Tasks 013 — Celular e app instalável

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T200 | Menu recolhível no celular | `Sidebar.tsx`, `layout.tsx` | FR-200, NFR-201, AC-201 | Vitest + E2E | [x] |
| T201 | Sem rolagem lateral em 360 px | páginas e tabelas | FR-201, AC-200 | E2E | [x] |
| T202 | Manifesto e ícones | `public/` | FR-202 | E2E | [x] |
| T203 | Service worker e faixa sem conexão | `sw.js`, `OfflineBanner.tsx`, `PwaRegister.tsx` | FR-203, FR-204, BR-200, AC-203 | Vitest + navegador | [x] |
| T204 | E2E de celular no CI | `e2e/mobile.spec.ts` | FR-205, AC-204 | E2E | [x] |
| T205 | Validação na vitrine e documentação | README, CURRENT_STATUS, ROADMAP | AC-202, AC-203 | navegador | [x] |

## Validação (2026-11-25)
- CI: 13 testes em tela de celular (Pixel 7) verdes — menu recolhível, manifesto e service worker servidos, e, em todas as páginas do menu, título à vista sem rolar, nenhuma rolagem lateral e axe sem violações graves.
- O axe de celular achou um problema real: tabelas que rolam para o lado sem nada focável dentro não podiam ser alcançadas pelo teclado (scrollable-region-focusable). Os 14 quadros de rolagem viraram regiões focáveis com nome.
- Vitrine (https://jh-2002.github.io/climate-platform/): service worker ativo com o escopo `/climate-platform/`, manifesto com 3 ícones, e depois da primeira visita o cache guarda a página, os dados da API gravada e os arquivos estáticos. Em 375 px, barra com "Menu" e o número de alertas vigentes, e o conteúdo logo abaixo.
- Sem conexão (AC-203): conferido pelo conteúdo dos caches e pelo teste da faixa; o painel do navegador usado na validação não permite desligar a rede.
