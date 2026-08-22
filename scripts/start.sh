#!/bin/sh
set -eu

alembic upgrade head
./scripts/create_readonly_user.sh
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

