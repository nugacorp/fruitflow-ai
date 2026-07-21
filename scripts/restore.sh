#!/usr/bin/env bash
# Restauracion. ENSAYAR EN SERVIDOR LIMPIO ANTES DE IR A PRODUCCION.
# Uso: ./scripts/restore.sh /backups/db_2026-07-21_0300.dump.gpg
set -euo pipefail

ARCHIVO=${1:?Falta la ruta del respaldo}
cd "$(dirname "$0")/.."
source .env

gpg --decrypt --batch --passphrase "$BACKUP_PASSPHRASE" "$ARCHIVO" > /tmp/restore.dump

docker compose -f docker/docker-compose.prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < /tmp/restore.dump

rm -f /tmp/restore.dump
echo "Restauracion completada. Verifica saldos antes de reanudar operaciones."
