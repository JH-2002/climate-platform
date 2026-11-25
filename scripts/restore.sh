#!/usr/bin/env bash
# Restaura um backup num banco NOVO e confere as tabelas principais (spec 011, FR-177, AC-176).
#   scripts/restore.sh climate_2026-11-25_0300.dump            -> banco "climate_restore"
#   scripts/restore.sh climate_2026-11-25_0300.dump climate_x  -> banco "climate_x"
# Não toca no banco em uso. Para trocar de banco, siga o manual (docs/operations/RUNBOOK.md).
set -euo pipefail

FILE="${1:?informe o arquivo de backup (ls dos backups: veja o RUNBOOK)}"
TARGET="${2:-climate_restore}"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)

if [[ ! "$TARGET" =~ ^[a-z_][a-z0-9_]*$ ]]; then
  echo "nome de banco inválido: $TARGET" >&2
  exit 2
fi

echo "Restaurando $FILE em $TARGET..."
"${COMPOSE[@]}" exec -T backup bash -c "
  set -euo pipefail
  test -f /backups/$FILE || { echo 'arquivo não encontrado em /backups' >&2; exit 2; }
  dropdb --if-exists $TARGET
  createdb $TARGET
  psql -d $TARGET -q -c 'CREATE EXTENSION IF NOT EXISTS postgis'
  pg_restore --no-owner --dbname=$TARGET /backups/$FILE
"

echo "Conferindo as contagens (backup restaurado x banco em uso):"
for table in hydro_risk_sectors risk_assessments official_alerts weather_forecasts climate_daily basins; do
  restored=$("${COMPOSE[@]}" exec -T backup psql -d "$TARGET" -tAc "SELECT count(*) FROM $table" 2>/dev/null || echo "—")
  live=$("${COMPOSE[@]}" exec -T backup psql -tAc "SELECT count(*) FROM $table" 2>/dev/null || echo "—")
  printf '  %-22s restaurado: %-10s em uso: %s\n' "$table" "$restored" "$live"
done
