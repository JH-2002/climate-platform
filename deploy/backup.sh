#!/usr/bin/env bash
# Backup diário do banco (spec 011, FR-177): pg_dump no formato custom, nome datado,
# retenção de BACKUP_KEEP_DAYS dias. Roda no contêiner "backup" (imagem do PostGIS).
set -euo pipefail

BACKUP_DIR=/backups
HOUR="${BACKUP_HOUR:-03}"
KEEP="${BACKUP_KEEP_DAYS:-14}"

log() {
  printf '{"timestamp":"%s","service":"backup","event":"%s"%s}\n' "$(date -Iseconds)" "$1" "${2:-}"
}

run_backup() {
  local name file start size
  name="climate_$(date +%Y-%m-%d_%H%M).dump"
  file="$BACKUP_DIR/$name"
  start=$(date +%s)
  if pg_dump --format=custom --no-owner --file="$file.tmp"; then
    mv "$file.tmp" "$file"
    size=$(stat -c %s "$file")
    log backup_done ",\"file\":\"$name\",\"bytes\":$size,\"duration_s\":$(( $(date +%s) - start ))"
  else
    rm -f "$file.tmp"
    log backup_failed ",\"file\":\"$name\""
    return 0
  fi
  find "$BACKUP_DIR" -name 'climate_*.dump' -mtime +"$KEEP" -print -delete \
    | while read -r old; do log backup_removed ",\"file\":\"$(basename "$old")\""; done
}

seconds_until_next() {
  local now today
  now=$(date +%s)
  today=$(date -d "today ${HOUR}:00" +%s)
  if (( now < today )); then
    echo $(( today - now ))
  else
    echo $(( $(date -d "tomorrow ${HOUR}:00" +%s) - now ))
  fi
}

mkdir -p "$BACKUP_DIR"
log backup_started ",\"hour\":\"$HOUR\",\"keep_days\":$KEEP"
if [[ "${BACKUP_ON_START:-0}" == "1" ]]; then
  run_backup
fi
while true; do
  sleep "$(seconds_until_next)"
  run_backup
done
