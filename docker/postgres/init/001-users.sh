#!/bin/bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_user="$POSTGRES_APP_USER" \
  --set=app_password="$POSTGRES_APP_PASSWORD" \
  --set=readonly_user="$POSTGRES_READONLY_USER" \
  --set=readonly_password="$POSTGRES_READONLY_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')\gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'readonly_user', :'readonly_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'readonly_user')\gexec
CREATE EXTENSION IF NOT EXISTS vector;
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user')\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'readonly_user')\gexec
GRANT CREATE, USAGE ON SCHEMA public TO :"app_user";
SQL

