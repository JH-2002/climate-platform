# Tasks 011 — Hardening

Legenda: `[ ]` pendente · `[x]` validada.

| ID | Tarefa | Arquivos | Critério de conclusão | Testes | Status |
|---|---|---|---|---|---|
| T180 | Cabeçalhos de segurança do frontend | `lib/security-headers.mjs`, `next.config.ts` | FR-170, BR-171, AC-170 | `security.test.ts` + navegador | [ ] |
| T181 | Cabeçalhos e limite de corpo na API | `core/security.py` | FR-171, FR-174, AC-174 | unitários + integração | [ ] |
| T182 | Limite de requisições com Redis | `core/rate_limit.py` | FR-172, FR-173, NFR-170, AC-171 a AC-173 | unitários + integração | [ ] |
| T183 | Validação da configuração de produção | `core/config.py` | FR-175, AC-175 | unitários | [ ] |
| T184 | Atualizações de dependências (Dependabot) | `pyproject.toml`, workflows | CI verde | CI | [ ] |
| T185 | Testes ponta a ponta com Playwright no CI | `frontend/e2e/`, `.github/workflows/ci.yml` | FR-179, AC-177 | E2E | [ ] |
| T186 | Imagens e pilha de produção com Caddy | `Dockerfile.prod`, `docker-compose.prod.yml`, `deploy/` | FR-176, NFR-171, NFR-173 | Docker local | [ ] |
| T187 | Backup e restauração | `deploy/backup.sh`, `scripts/restore.sh` | FR-177, AC-176 | Docker local | [ ] |
| T188 | Metas de desempenho medidas | `scripts/perf_check.py` | FR-180 | Docker local | [ ] |
| T189 | Manual de operação e documentação | `docs/operations/RUNBOOK.md` | FR-178 | revisão | [ ] |
