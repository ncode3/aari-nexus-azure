#!/bin/sh
set -eu

: "${DATABASE_ADMIN_URL:?DATABASE_ADMIN_URL is required}"
: "${POSTGRES_READONLY_USER:=aari_readonly}"

ADMIN_URL=$(printf '%s' "$DATABASE_ADMIN_URL" | sed 's|postgresql+psycopg://|postgresql://|')
psql "$ADMIN_URL" --set=readonly_user="$POSTGRES_READONLY_USER" <<'SQL'
GRANT USAGE ON SCHEMA public TO :"readonly_user";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"readonly_user";
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO :"readonly_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO :"readonly_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO :"readonly_user";
GRANT EXECUTE ON FUNCTION log_mcp_audit(text,text,text,uuid,text,boolean,jsonb)
  TO :"readonly_user";
SQL
