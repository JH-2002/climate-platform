# Testes ponta a ponta (spec 011, FR-179)

Playwright contra o build de produção do Next, com a API simulada pelas respostas gravadas em
`fixtures/` (um arquivo por teste). Nenhuma chamada sai para a internet: o mapa de fundo e o
relevo ficam em branco, e o relógio do navegador fica parado no instante da gravação.

O Playwright não está no `package.json`: o job `e2e` do CI instala a versão fixada ali.

## Rodar no CI
Automático em todo push e PR (job "Ponta a ponta (Playwright)"). Em caso de falha, o relatório
com o rastro de cada teste fica nos artefatos do job (`playwright-report`).

## Gravar de novo os dados
Com a plataforma de desenvolvimento no ar e com dados (`docker compose up -d`):

```bash
docker compose --profile e2e run --rm e2e-record
```

Os testes rodam contra `http://frontend:3000` e regravam `e2e/fixtures/*.json`. O teste de
relatórios gera um relatório de verdade e o do Laboratório roda uma simulação. Revise o diff
antes do commit: coleções grandes são cortadas em 60 itens.

Teste novo: escreva o teste, grave, e confira se `fixtures/<nome-do-teste>.json` apareceu.
