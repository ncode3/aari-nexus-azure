#!/bin/sh
set -eu

: "${DATABASE_ADMIN_URL:?DATABASE_ADMIN_URL is required}"
: "${MINIO_ENDPOINT:?MINIO_ENDPOINT is required}"
: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"

BACKUP_DIR=${1:-"backups/$(date -u +%Y%m%dT%H%M%SZ)"}
mkdir -p "$BACKUP_DIR/minio"
PG_URL=$(printf '%s' "$DATABASE_ADMIN_URL" | sed 's|postgresql+psycopg://|postgresql://|')
case "$MINIO_ENDPOINT" in
  http://*|https://*) MINIO_URL=$MINIO_ENDPOINT ;;
  *) MINIO_URL="http://$MINIO_ENDPOINT" ;;
esac
pg_dump --format=custom --no-owner --file="$BACKUP_DIR/postgresql.dump" "$PG_URL"
mc alias set aari-backup "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mirror --overwrite aari-backup/aari-documents "$BACKUP_DIR/minio/aari-documents"
mc mirror --overwrite aari-backup/aari-rejected "$BACKUP_DIR/minio/aari-rejected"
printf '%s\n' "$BACKUP_DIR"
