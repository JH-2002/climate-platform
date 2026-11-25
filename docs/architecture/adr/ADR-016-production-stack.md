# ADR-016 — Pilha de produção: Docker Compose com Caddy

- Status: **Aceita** (2026-11-25)
- Fase: 11 · Spec: [011](../../../specs/011-hardening/spec.md)

## Contexto
A plataforma precisa ficar pública num servidor ainda não escolhido. Ela é composta por API
(FastAPI), worker e agendador (Celery), PostgreSQL/PostGIS, Redis e o frontend (Next.js). O
volume de acesso esperado é pequeno a médio, e a operação é feita por uma pessoa.

## Decisão
1. **Docker Compose num único servidor Linux**, com um arquivo de produção separado do de desenvolvimento.
2. **Caddy como proxy de borda**: HTTPS automático com Let's Encrypt, HSTS, compressão e redirecionamento HTTP→HTTPS, com um `Caddyfile` de poucas linhas.
3. **Só o Caddy publica portas** (80/443). Banco e Redis ficam na rede interna; o Redis passa a exigir senha.
4. **Limite de requisições e cabeçalhos na própria aplicação**, além do proxy, para valer em qualquer hospedagem.
5. **Backup local diário com `pg_dump`** e cópia externa recomendada no manual.

## Motivos
- Compose já é a forma de rodar o projeto; produção fica com a mesma topologia, o que reduz surpresas.
- Caddy resolve TLS sem configuração manual de certificados, ao contrário de Nginx + Certbot.
- Kubernetes ou serviços gerenciados acrescentam custo e operação desproporcionais ao tamanho do projeto. A troca continua possível: as imagens são as mesmas.

## Consequências
- Um servidor é um ponto único de falha; o manual cobre restauração a partir do backup.
- Atualizar é `git pull` + `docker compose -f docker-compose.prod.yml up -d --build`, com as migrações rodando antes da API.
