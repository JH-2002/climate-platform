# Spec 014 — Atualização das dependências

> Status: **Concluída** (2026-11-25) · Fase: 14

## Contexto
Desde a Fase 1 ficaram registradas pendências técnicas: Vitest 2, Next 15, mypy fixo em 1.13 e
versões principais que o Dependabot ignora de propósito. Um levantamento automático (workflow
"Gerar lockfiles", agora com `npm outdated` e `pip list --outdated`) mostrou onze versões
principais atrasadas.

## Decisões
| Pacote | De → para | Decisão |
|---|---|---|
| Vitest, @vitejs/plugin-react, jsdom, @testing-library/jest-dom | 2 → 5, 4 → 6, 25 → 31, 6 → 8 | **Atualizados.** O jsdom novo calcula nomes acessíveis sem o espaço inicial de textos só para leitores de tela; os nomes passaram a não depender disso (vírgula no contador de alertas, nome explícito nos botões "Por quê?"). |
| Recharts | 2 → 3 | **Atualizado.** A linha 2 não recebe mais correções. |
| Next, eslint-config-next | 15 → 16 | **Atualizados.** Configuração flat nativa do ESLint; build de produção com Turbopack; `next dev --webpack` no Docker (o Turbopack não percebe mudanças em pastas do Windows montadas no contêiner). As regras novas do React Hooks 7 apontaram 11 pontos: 8 reescritos sem `setState` em efeito nem ref na renderização; 3 leituras só do navegador ficaram em efeito, com a razão na linha. |
| mypy, ruff | 1.13 → 2.4, 0.16 → 0.17 | **Atualizados** (continuam fixos). O mypy 2 achou uma variável reaproveitada com consultas de formatos diferentes. |
| ESLint | 9 → 10 | **Adiado.** Alguns plugins do `eslint-config-next` ainda não declaram suporte ao ESLint 10. |
| Tailwind CSS | 3 → 4 | **Adiado.** A versão 4 troca o arquivo de configuração por CSS; é uma migração de estilo inteira, com revisão visual de todas as telas. |
| TypeScript | 5.9 → 7 | **Adiado.** Compilador novo (reescrito em Go); esperar o suporte do Next e do typescript-eslint. |
| @types/node | 22 → 26 | **Mantido em 22**, igual ao Node das imagens e do CI. |

## Ambiente local
- O contêiner de desenvolvimento do frontend atualiza o `node_modules` do volume sozinho quando o `package-lock.json` muda (`scripts/dev-entrypoint.sh`).
- Depois de atualizar o repositório: `docker compose up -d --build`.

## Critérios de aceite
- **AC-210** CI verde (backend, frontend, ponta a ponta em computador e celular) com as versões novas.
- **AC-211** Vitrine publicada com o build do Next 16, todas as páginas do menu carregando.
