#!/bin/sh
set -eu

BACKUP_DIR=${1:?usage: scripts/restore.sh BACKUP_DIRECTORY}
: "${DATABASE_ADMIN_URL:?DATABASE_ADMIN_URL is required}"
: "${MINIO_ENDPOINT:?MINIO_ENDPOINT is required}"
: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"

test -f "$BACKUP_DIR/postgresql.dump"
PG_URL=$(printf '%s' "$DATABASE_ADMIN_URL" | sed 's|postgresql+psycopg://|postgresql://|')
case "$MINIO_ENDPOINT" in
  http://*|https://*) MINIO_URL=$MINIO_ENDPOINT ;;
  *) MINIO_URL="http://$MINIO_ENDPOINT" ;;
esac
pg_restore --clean --if-exists --no-owner --dbname="$PG_URL" "$BACKUP_DIR/postgresql.dump"
mc alias set aari-restore "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
test ! -d "$BACKUP_DIR/minio/aari-documents" || \
  mc mirror --overwrite "$BACKUP_DIR/minio/aari-documents" aari-restore/aari-documents
test ! -d "$BACKUP_DIR/minio/aari-rejected" || \
  mc mirror --overwrite "$BACKUP_DIR/minio/aari-rejected" aari-restore/aari-rejected
