#!/usr/bin/env bash
# Respaldo diario cifrado de PostgreSQL + sincronizacion de documentos.
# Cron sugerido: 0 3 * * * /opt/fruitflow/scripts/backup.sh >> /var/log/fruitflow-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
source .env

STAMP=$(date +%F_%H%M)
DESTINO=/backups
mkdir -p "$DESTINO"

docker compose -f docker/docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
  | gpg --symmetric --batch --yes --passphrase "$BACKUP_PASSPHRASE" \
  > "${DESTINO}/db_${STAMP}.dump.gpg"

if command -v rclone >/dev/null; then
  rclone sync "$DESTINO" "b2:${B2_BUCKET}/db" --transfers 4
  rclone sync "minio:${MINIO_BUCKET}" "b2:${B2_BUCKET}/docs"
fi

find "$DESTINO" -name '*.gpg' -mtime +30 -delete
echo "Respaldo completado: db_${STAMP}.dump.gpg"
