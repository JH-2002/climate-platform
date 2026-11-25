# Manual de operação — produção

> Spec 011 (FR-178) · ADR-016. Pilha: `docker-compose.prod.yml` (Caddy → Next → API/Celery → PostgreSQL/PostGIS e Redis).

## 1. Requisitos do servidor
- Linux de 64 bits com Docker Engine 24+ e o plugin `docker compose`.
- 2 vCPU, 4 GB de RAM e 30 GB de disco no mínimo. Os limites somados dos contêineres dão cerca de 4,4 GB, e o worker usa mais memória quando recalcula o terreno.
- Portas 80 e 443 abertas para a internet. As outras ficam fechadas: nenhum outro serviço publica porta.
- Um domínio com registro `A` (e `AAAA`, se houver IPv6) apontando para o servidor.

## 2. Primeira instalação
```bash
git clone https://github.com/JH-2002/climate-platform.git
cd climate-platform
cp .env.prod.example .env.prod
# Edite o .env.prod: DOMAIN, ACME_EMAIL, POSTGRES_PASSWORD e REDIS_PASSWORD.
# Gere as senhas com: openssl rand -base64 32
chmod 600 .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
- O serviço `migrate` aplica as migrações e encerra. Só depois sobem a API, o worker e o agendador.
- O agendador dispara as coletas iniciais: subprefeituras, Defesa Civil, INMET, previsão, reanálise (começa a preencher 1991–hoje aos poucos) e o recorte do relevo (cerca de 47 MB, uma vez).
- O Caddy obtém o certificado no primeiro acesso a `https://DOMAIN`. Se falhar, veja a seção 7.

**Testar a pilha na própria máquina (Windows):** `powershell -ExecutionPolicy Bypass -File scripts\validar-producao.ps1` cria um `.env.prod` de teste (`DOMAIN=localhost`, portas 8080/8443, senhas aleatórias), sobe a pilha, confere saúde e cabeçalhos, faz backup e restauração e grava tudo em `validacao-producao.log`. À mão: use `DOMAIN=localhost`, `CADDY_HTTP_PORT=8080` e `CADDY_HTTPS_PORT=8443` e abra `https://localhost:8443`. O Caddy usa uma CA local, então o navegador vai pedir para aceitar o certificado.

## 3. Verificar a saúde
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
curl -fsS https://DOMAIN/api/v1/health    # processo da API
curl -fsS https://DOMAIN/api/v1/health/ready   # banco, PostGIS, Redis e worker
```
- Página **Estado do sistema** (`/status`): frescor de cada fonte e a última coleta.
- Logs em JSON, com rotação de 10 MB × 3 por contêiner. Para ver: `docker compose -f docker-compose.prod.yml logs -f --tail=100 api worker beat`.

## 4. Atualizar
```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
As migrações rodam antes da API. Antes de uma atualização com migração nova, faça um backup manual (seção 5).

## 5. Backup e restauração
- **Automático:** o serviço `backup` grava `climate_AAAA-MM-DD_HHMM.dump` todo dia às `BACKUP_HOUR` (horário de Brasília) no volume `backups` e apaga os arquivos com mais de `BACKUP_KEEP_DAYS` dias (padrão: 14).
- **Manual:**
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec backup \
    bash -c 'pg_dump --format=custom --no-owner --file=/backups/climate_manual_$(date +%Y-%m-%d_%H%M).dump'
  ```
- **Listar:** `docker compose -f docker-compose.prod.yml --env-file .env.prod exec backup ls -lh /backups`.
- **Testar a restauração (faça uma vez por mês):**
  ```bash
  scripts/restore.sh climate_2026-11-25_0300.dump
  ```
  O script restaura num banco novo (`climate_restore`), sem tocar no banco em uso, e mostra as contagens das tabelas principais lado a lado. As tabelas que mudam o tempo todo (previsão, avaliações de risco) podem diferir um pouco; setores e bacias devem bater.
- **Trocar o banco em uso pelo restaurado** (só em caso de perda):
  1. Pare a aplicação: `docker compose -f docker-compose.prod.yml --env-file .env.prod stop api worker beat frontend`.
  2. Restaure no banco principal:
     ```bash
     docker compose -f docker-compose.prod.yml --env-file .env.prod exec backup \
       bash -c 'dropdb climate && createdb climate && psql -d climate -c "CREATE EXTENSION postgis" && pg_restore --no-owner -d climate /backups/ARQUIVO.dump'
     ```
  3. Suba de novo com `up -d`.
- **Cópia para fora do servidor (recomendado):** o volume `backups` está no mesmo disco. Copie os arquivos todo dia para um armazenamento externo, por exemplo `rclone copy` do diretório do volume (`docker volume inspect climate-platform-prod_backups`) para um bucket S3 ou B2.

## 6. Voltar uma versão
```bash
git log --oneline -10                  # escolha o commit anterior
git checkout <commit>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
- Se a versão nova trouxe migração, desfaça a migração **antes** do checkout:
  `docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm migrate alembic downgrade -1`.
- Em dúvida, restaure o backup feito antes da atualização (seção 5).

## 7. Problemas comuns
| Sintoma | O que verificar |
|---|---|
| Certificado não sai | O DNS aponta para o servidor? As portas 80 e 443 estão abertas? O `ACME_EMAIL` está preenchido? `docker compose ... logs caddy` |
| `/api/v1/health/ready` falha no worker | `docker compose ... logs worker`. Se o worker morreu por falta de memória, suba `mem_limit` do worker |
| API não sobe e o log diz "16 caracteres" | A senha do banco no `.env.prod` é fraca ou é a de exemplo (FR-175) |
| Visitantes recebem 429 | O limite é por IP. Ajuste `RATE_LIMIT_GENERAL` / `RATE_LIMIT_HEAVY` e reinicie a API. Se todos os acessos aparecem com o mesmo IP, o proxy não está repassando o `X-Forwarded-For` |
| Fonte "Indisponível" em `/status` | Veja a última mensagem de erro na própria página e os logs do worker. Fontes externas param às vezes; os alertas de qualidade dos dados avisam na página Alertas |
| Disco cheio | `docker system df`. Os backups são apagados em 14 dias, os relatórios em 7 e as simulações em 30 |

## 8. Trocar segredos
1. Gere a nova senha e altere no `.env.prod`.
2. Banco: `docker compose ... exec db psql -U climate -c "ALTER USER climate PASSWORD 'NOVA'"`.
3. Recrie os serviços que leem a senha: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate`.
4. Redis: basta recriar (a senha está no comando do serviço).

## 9. Metas de desempenho (FR-180)
Com a pilha no ar e os dados carregados:
```bash
docker compose exec backend python scripts/perf_check.py                 # desenvolvimento
docker compose -f docker-compose.prod.yml --env-file .env.prod exec api python scripts/perf_check.py
```
O resultado da última medição fica registrado em `specs/011-hardening/tasks.md`.
