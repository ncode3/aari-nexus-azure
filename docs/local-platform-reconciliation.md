# Local operator and the portable data platform

Reviewed PR #1 at `d8823d8` and PR #35's original runtime at `2afcfb2` before
extending local storage. No replacement database, vector service, object-storage
server, Redis instance, or business ingestion pipeline is introduced here.

| Responsibility | Owner and boundary |
| --- | --- |
| Bot memories and approval packages | Existing `MemoryStore` SQLite schema; private operator state, not a second student roster |
| Small operator attachments | Content-addressed files below the same recovery directory; filename search only, maximum 1 MiB |
| Normalized students, cohorts, financial records, business documents and ingestion lineage | PR #1 PostgreSQL/pgvector and private MinIO; not migrated or made authoritative by this runtime |
| Cohort Desk / Power Apps | Existing application links remain. SharePoint remains authoritative; local profile disables live Graph reads |
| Operator HTTP | `app.local_api`, loopback port 8765, `/local/*`, bearer token and explicit allowed chat |
| Business platform HTTP | PR #1 `app.main`, port 8000, `/api/v1/*`; its migrations, identity and bounded routes remain separate |

PR #1 replaces `app/main.py`; PR #35 originally changed that same module.
The executable local entry point now creates `app.local_api:create_app` instead,
so combining the branches must retain PR #1's platform `app.main`, migrations,
compose file, and system-of-record ownership. Do not replace those with SQLite.
Keep legacy Telegram polling disabled in the platform process when running a
separate operator. Both cannot own one production Telegram token.

This is a scope/entry-point reconciliation, not a claim that both branches have
been merged or their services integration-tested. This machine currently has WSL
but no Docker or Podman executable was found. PR #1's database/MinIO acceptance
still requires its healthy container runtime and integration tests. Move business
documents through its ingestion API only after those tests pass; no implicit
SQLite-to-PostgreSQL or attachment-to-MinIO migration runs here.

Do not infer that local managed-identity access exists. A separately approved
Graph authentication mechanism is needed for live local Cohort Desk reporting.
The local operator does not copy applicant records or send them to a model.
