# Current-State Assessment

## Repository role

`ncode3/aari-nexus-azure` currently contains an Azure-oriented Telegram operations service and
the first production evidence-ingestion utilities. The repository is public, so raw student
records and credentials must remain outside Git.

## Existing reusable components

- FastAPI runtime in `app/main.py`
- Environment parsing and secret redaction in `app/config.py` and `app/arbiter.py`
- Dockerfile and minimal Compose configuration
- Azure Blob assessment upload in `app/assessment_flow.py`
- XLSX and CSV parsing for the 33-response technical-skills baseline
- Weekly DOCX parsing in `app/weekly_report_ingestion.py`
- Evidence analytics and completeness logic in `app/evidence_analytics.py`
- CLI ingestion scripts in `scripts/`
- Pulumi definitions for the existing Azure Container Apps deployment
- 34 unit tests covering the bot, assessment, evidence, and weekly-report behavior

## Current Azure workflow

The existing scripts use `AZURE_STORAGE_ACCOUNT_URL` plus `DefaultAzureCredential`, or an
optional Blob connection string, and store raw and processed evidence in Azure Blob Storage.
Pulumi provisions Azure Blob Storage, managed identity, Key Vault, Azure OpenAI configuration,
and Container Apps. Azure Blob is currently the file-first authority.

The portable platform will retain a thin HTTP adapter for these jobs. Azure will submit files and
metadata to the API and poll job status; it will not receive PostgreSQL or MinIO credentials.

## Existing ingestion and data formats

- Technical-skills assessments: CSV/XLSX, question-level normalization, SHA-256 lineage
- Weekly progress reports: DOCX section extraction and evidence classification
- Evidence analytics: JSON aggregate outputs and reporting completeness
- Intake document filename classification
- SQLite operational memory for the Telegram MVP
- No current PDF parser, financial importer, normalized identity database, migration framework,
  PostgreSQL repository layer, MinIO object storage, or MCP server

No Excel, CSV, PDF, JSON, or raw student-response binaries are committed to this repository.
The authoritative source files currently live outside Git and in private Azure Blob Storage.

## Existing schemas and financial designs

The repository has Python dictionaries for assessments, activity evidence, competencies,
Coursera data, sponsor attribution, and career readiness. It has no relational schema or
financial database implementation. SQLite stores only unstructured memories and action
packages. Money is not modeled.

## Existing environment variables

The current `.env.example` contains placeholders for Telegram, Azure OpenAI, PEP, SQLite,
Azure Blob, Application Insights, Key Vault, and managed identity. No populated `.env` is
tracked. The portable stack adds PostgreSQL, MinIO, API, upload-limit, optional Redis, and
read-only MCP configuration while keeping Azure variables optional.

## Docker and testing

The current Docker image uses Python 3.11 and runs only FastAPI/Telegram. Compose contains one
service and no persistence or health checks. The new image uses Python 3.12 and Compose adds
PostgreSQL 16 with pgvector, MinIO, bucket initialization, API migration startup, an optional
Redis profile, persistent volumes, and localhost-only development ports.

Tests currently use pytest/unittest without PostgreSQL or MinIO integration containers. The new
suite retains these tests and adds unit and Compose-backed integration coverage.

## Security assessment

- No committed secrets were found by pattern scan.
- `.env` and virtual environments are ignored.
- Pulumi requires Azure OpenAI values as encrypted secrets.
- Existing Blob scripts can accept connection strings; the portable core will not depend on them.
- The current API validates Azure/Telegram configuration at import time, preventing a
  credentials-free local start.
- SQLite has no application/read-only role separation.
- There is no audit table, upload MIME/size enforcement, object-store isolation, or database
  least privilege.

## Replacement and compatibility plan

- PostgreSQL replaces SQLite and JSON files as the structured system of record.
- MinIO replaces Azure Blob as the authoritative original-document store.
- Existing Azure Blob code remains available as a compatibility adapter during migration.
- Existing assessment and evidence parsers are wrapped by adapter-based ingestion services.
- Telegram and Azure OpenAI modules remain optional and are not required by the base platform.
- No working code is deleted or archived in this migration.
