# ADR-008 — Locais salvos no navegador até existir autenticação

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
A spec 003 pede locais salvos (casa, trabalho). A plataforma ainda não tem contas de usuário; criar autenticação agora é maior que o problema.

## Decisão
Locais ficam no `localStorage` do navegador, com leitura/escrita protegidas por `try/catch` e validação de coordenadas. A URL carrega o local selecionado, para compartilhar.

## Consequências
Locais não sincronizam entre dispositivos. A tabela `locations` (por usuário) entra com a fase de usuários; o formato salvo no navegador poderá ser importado.
