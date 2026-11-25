# Tasks 012 — Vitrine pública

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T190 | Chaves dos arquivos (gravação e leitura) | `lib/demo.ts` | AC-194 | Vitest | [x] |
| T191 | Cliente da API no modo demonstração | `lib/api-client.ts` | FR-190, FR-191 | Vitest | [x] |
| T192 | Faixa de demonstração e URLs diretas | `DemoBanner.tsx`, `features/geo`, `features/analytics` | FR-192, BR-190 | Vitest | [x] |
| T193 | Export estático com basePath | `next.config.ts` | FR-193 | build no CI | [x] |
| T194 | Coleta no CI | `scripts/demo_collect.py` | FR-194 | workflow | [x] |
| T195 | Roteiro de gravação | `frontend/demo/` | FR-195 | workflow | [x] |
| T196 | Workflow e publicação | `.github/workflows/demo.yml` | FR-196, NFR-190, NFR-191 | workflow | [x] |
| T197 | Validação no link público e documentação | README, CURRENT_STATUS, ROADMAP | AC-190 a AC-193 | navegador | [x] |

## Validação no Actions (2026-11-25, PR #42)
- Coleta real nos executores do GitHub: GeoSampa (setores, manchas, ocorrências), subprefeituras, previsão, IAG/USP, relevo, Defesa Civil, avisos do INMET, risco e alertas do sistema funcionaram. O cadastro de estações do INMET é cortado pelo servidor do INMET (ReadError/ReadTimeout) e o Open-Meteo limita a reanálise (HTTP 429): o banco passa a ficar guardado no cache do Actions entre as execuções, então a reanálise vai se completando (7 pontos na terceira execução) e o que já foi coletado não se perde.
- Gravação: 7 roteiros em 3,4 min, cerca de 2.000 arquivos (793 setores com detalhe e terreno, bacias, blocos do relevo, cenários prontos). Site de 40 MB (NFR-191: até 60 MB). Workflow completo em cerca de 20 min (NFR-190).
- Achados e corrigidos durante a validação: `runner.temp` não vale no `env` do job; detalhes em série estouravam o tempo (agora 8 em paralelo); o reinício do Playwright apagava a gravação; um clique travava no botão da explicação (agora pela URL).

## Validação no link público (2026-11-25)
- https://jh-2002.github.io/climate-platform/ no ar: as 11 páginas do menu carregam com dados, faixa de demonstração com o horário da gravação, alerta real da Defesa Civil na faixa de alertas.
- Laboratório: cenário pronto devolve o resultado gravado (AC-191); valor alterado mostra a mensagem de FR-191 (AC-192).
- Achados e corrigidos no link público (PR #43): o gravador só aceitava 200 e a criação de simulação responde 201; a previsão do tempo não era gravada quando a página seguia antes de ler a resposta (agora o roteiro busca de novo o que faltou).
- Limitação conhecida: o cadastro de estações do INMET não responde aos servidores do GitHub; a vitrine mostra "nenhuma estação cadastrada" e a página Estado do sistema registra a falha.
