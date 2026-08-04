# AARI Portable Data Platform

This repository provides the self-hosted system of record for the Atlanta AI & Robotics
Initiative. PostgreSQL 16 stores normalized program data, MinIO stores original documents,
FastAPI exposes bounded application operations, and a separate read-only MCP server gives Codex
controlled access. Azure can submit work through HTTP, but no cloud database is authoritative.

The former Azure/Telegram modules remain in place as optional compatibility code. They are not
required to start or operate the base platform.

## Architecture

```text
Gmail / Forms / Excel / CSV / PDFs / APIs
                    |
          validate / normalize / deduplicate
             |                    |
        PostgreSQL 16            MinIO
             +---------+----------+
                       |
                    FastAPI
                  /         \
          read-only MCP    dashboards
```

PostgreSQL includes pgvector, but embeddings are disabled until an approved provider is
configured. Redis is also disabled unless the `cache` Compose profile is selected.

## Quick start

Requirements: Docker with Compose v2 (or Podman Compose) and GNU Make.

```bash
cp .env.example .env
# Replace every local development password before a shared deployment.
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

The API startup runs `alembic upgrade head`; it never drops or recreates existing data. Local
development ports bind only to `127.0.0.1`.

```bash
make setup
make up
make seed
make test
make down
```

Enable Redis only when an approved cache use exists:

```bash
docker compose --profile cache up -d redis
```

## Import existing data

Import a supported file or directory recursively:

```bash
make import FILE="$HOME/Downloads/aari-evidence"
.venv/bin/python scripts/import_directory.py report.pdf --classification internal
```

Supported base formats are CSV, XLSX, JSON, and PDF. The reusable pipeline validates size and
MIME type, calculates SHA-256, stores the original in MinIO, parses and normalizes supported
content, writes lineage and audit events, and rejects checksum duplicates.

The existing assessment command remains supported; its parser is now reusable by the database
assessment importer:

```bash
python scripts/ingest_assessment.py \
  --input "$HOME/Downloads/Technical Skills Assessment Survey (Responses).xlsx" \
  --cohort summer-2026-data-center \
  --stage baseline \
  --instrument-version 2026-01
```

Never put raw student data under `data/samples` or commit it. `data/incoming`, `data/processed`,
and `data/rejected` are ignored except for placeholder files.

Ingest the standardized downloaded Week 2 student reports into the private Azure compatibility
store, preserving conflicting source provenance without double-counting it:

```bash
AZURE_STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net \
  python scripts/ingest_student_reports.py --downloads "$HOME/Downloads" --upload

AZURE_STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net \
  python scripts/regenerate_student_report_analytics.py \
  --downloads "$HOME/Downloads" --upload
```

Both commands default to the private `artifacts` container, use `DefaultAzureCredential`, classify
student data as internal, and set `index_allowed=false`.

## API

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`. Versioned routes
are under `/api/v1` and include documents, ingestion jobs, students, progress, cohorts, metrics,
grants, financial summary, and bounded search. Responses include `X-Request-ID`.

Azure submission:

```bash
python scripts/submit_from_azure.py staged-report.pdf \
  --source-identifier "azure-workflow/run-123"
```

See [Azure integration](docs/azure-workflow-integration.md).

## Codex MCP

The MCP process uses `READONLY_DATABASE_URL`. That role receives SELECT privileges and permission
to execute one security-definer audit function; it cannot insert, update, delete, create, or run
arbitrary SQL through an MCP tool.

```bash
READONLY_DATABASE_URL='postgresql+psycopg://...' \
  .venv/bin/python -m mcp_server.server
```

Codex configuration example:

```toml
[mcp_servers.aari]
command = "/absolute/path/to/.venv/bin/python"
args = ["-m", "mcp_server.server"]
cwd = "/absolute/path/to/aari-nexus-azure"

[mcp_servers.aari.env]
READONLY_DATABASE_URL = "postgresql+psycopg://aari_readonly:REDACTED@localhost:5432/aari"
```

## Operations

```bash
make migrate
make migration MESSAGE="describe change"
make lint
make test
make backup
make restore FILE=backups/20260731T120000Z
python scripts/verify_environment.py
```

Relevant documentation:

- [Current-state assessment](docs/current-state-assessment.md)
- [Platform architecture](docs/architecture.md)
- [Security model](docs/security-model.md)
- [Data governance](docs/data-governance.md)
- [Backup and recovery](docs/backup-and-recovery.md)
- [Azure workflow integration](docs/azure-workflow-integration.md)
