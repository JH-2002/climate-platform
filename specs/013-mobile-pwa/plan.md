# Plan 013 — Celular e app instalável

## Decisões
- **Service worker escrito à mão** (`public/sw.js`, cerca de 100 linhas), sem biblioteca: as regras são poucas (estáticos, telas, API) e o mesmo arquivo serve a plataforma e a vitrine. O `basePath` chega pela URL de registro (`sw.js?base=/climate-platform`).
- **Registro só em produção**, num componente cliente (`components/layout/PwaRegister.tsx`), para não prender versões antigas durante o desenvolvimento.
- **Ícones gerados de um SVG próprio** (gota sobre a grade da cidade) com `rsvg-convert`, versionados em `public/icons/`.
- **Menu**: o mesmo `Sidebar` com dois modos (barra + painel no celular, coluna no computador), sem duplicar a lista de links.
- **Sem conexão**: `navigator.onLine` e os eventos `online`/`offline` (`features/offline/useOnline.ts`); ao voltar, `queryClient.refetchQueries()`.

## Arquivos
| Arquivo | Conteúdo |
|---|---|
| `components/layout/Sidebar.tsx` | Barra, botão e painel do celular |
| `components/layout/OfflineBanner.tsx`, `features/offline/useOnline.ts` | Faixa e estado da conexão |
| `components/layout/PwaRegister.tsx` | Registro do service worker |
| `public/sw.js`, `public/manifest.webmanifest`, `public/icons/*` | PWA |
| `app/layout.tsx` | Manifesto, cor do tema e viewport |
| `e2e/mobile.spec.ts`, `playwright.config.ts` | Projeto de celular |

## Testes
- Vitest: menu (abrir, fechar com Esc, foco, `aria-expanded`), faixa sem conexão, URL de registro com e sem `basePath`.
- E2E (celular): menu, rolagem lateral e axe em todas as páginas; manifesto e service worker servidos.
