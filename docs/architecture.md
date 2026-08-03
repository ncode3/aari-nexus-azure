# Platform Architecture

## Authoritative services

```text
Gmail / Forms / Excel / CSV / PDFs / APIs
                    |
                    v
          adapter-based ingestion
 discover -> validate -> checksum -> store -> parse
       -> normalize -> deduplicate -> lineage -> audit
             |                         |
             v                         v
       PostgreSQL 16                 MinIO
     structured records          original documents
             +-----------+-------------+
                         |
                      FastAPI
                    /         \
          read-only Codex MCP  dashboards
```

PostgreSQL is the structured system of record. MinIO is the binary system of record. Azure may
run a workflow and stage a file, but submits it over HTTP and receives no persistence credential.

## Runtime services

- `postgres`: PostgreSQL 16 from the pgvector image, persistent volume, localhost-only
  development port, application and read-only roles.
- `minio`: S3-compatible object storage with persistent volume and private document/rejected
  buckets.
- `minio-init`: idempotently creates buckets, disables anonymous access, and installs the
  application’s bucket-scoped policy.
- `api`: Python 3.12 FastAPI image; runs forward-only Alembic migrations before serving.
- `redis`: optional `cache` profile, not referenced by normal request handling.
- `test`: optional `test` profile with disposable integration and backup/restore verification.

## Data model

Canonical identity begins at `people`; students and partner contacts are roles. Cohort,
attendance, assessment, certification, learning-platform, project, equipment, grant, finance,
document, workflow, ingestion, and audit tables use UUID keys and relational constraints.
Financial amounts use fixed-precision numeric columns.

Original binaries never enter PostgreSQL. `documents` and `document_versions` point to private
MinIO objects by bucket and key. `document_chunks` stores extracted text and an optional pgvector
embedding. The base embedding provider is disabled and requires no external service.

Calculated progress, cohort, and financial results are database views rather than copied
performance fields.

## API boundary

The API exposes bounded, versioned operations under `/api/v1`. Uploads are size- and MIME-limited.
Filenames are sanitized. Request IDs are returned on every response. Search is parameterized and
result-limited; there is no arbitrary SQL endpoint.

## MCP boundary

The MCP process connects as `aari_readonly`. Tools use fixed parameterized statements, cap result
counts, omit direct contact fields, and exclude restricted documents. Its sole non-SELECT
permission is a constrained security-definer function that appends an MCP audit event.

## Legacy compatibility

The Telegram operator, Arbiter, Azure OpenAI client, Azure Blob assessment utilities, and Pulumi
deployment remain in the repository. The Telegram loop starts only when
`ENABLE_TELEGRAM_BOT=true`; it is not a dependency of the portable platform. SQLite memory is a
legacy operator store and will be migrated separately rather than silently discarded.

