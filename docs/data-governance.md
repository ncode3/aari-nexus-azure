# Data Governance

## Authority and classification

PostgreSQL is authoritative for structured records. MinIO is authoritative for original files.
Azure Blob may temporarily stage migration inputs but is not the system of record.

Classifications:

- `public`: approved for public release, still private in MinIO by default.
- `internal`: program, learner, partner, and operational records.
- `restricted`: invoices, sensitive finance, credentials evidence, or specially controlled data.

No document is sent to an embedding or generative-AI provider by default. The disabled embedding
provider fails closed. Approval must identify the classification, provider, model, purpose,
retention behavior, and responsible owner.

## Lineage and retention

Every document records its filename, content type, size, SHA-256, source system, source identifier,
object key, version, classification, retention category, ingestion time, and processing status.
Derived chunks link to a document version. Deletable business records use `deleted_at`; immutable
audit and ingestion records do not.

Retention schedules are represented by `retention_category`; actual purge automation must not be
enabled until AARI approves category durations and legal holds. Backups inherit the highest
classification of their contents.

## Identity

`people` is the canonical person entity. Student, project, cohort, certification, partner-contact,
and equipment relationships reference it rather than cloning names. External IDs are JSONB only
for source-specific identifiers; stable AARI identity remains relational.

## Analytics

Performance metrics are calculated in views or services. Raw student evidence and direct contact
details are not sponsor-facing. Aggregates must retain source lineage and must distinguish
reported activity from verified evidence.

