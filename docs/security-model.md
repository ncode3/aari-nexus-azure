# Security Model

## Trust boundaries

PostgreSQL and MinIO are on the Compose private network. Their development ports and the API bind
to localhost. Buckets are explicitly private. CORS is disabled by default. The API is the only
supported write path for remote workflow engines.

## Identities and least privilege

- `aari_admin` initializes extensions, migrations, backups, and grants.
- `aari_app` owns application tables and performs normal reads and writes.
- `aari_readonly` has SELECT access and may execute only `log_mcp_audit`, a constrained
  security-definer function. It has no table mutation or DDL privileges.
- `aari_app` has a MinIO policy limited to the documents and rejected buckets.
- MinIO root credentials are for initialization, backup, and recovery only.

Replace all `.env.example` development passwords before shared use. Keep `.env`, database dumps,
raw evidence, tokens, OAuth credentials, and object-store credentials outside Git.

## Application controls

- Uploads have a configurable size ceiling and MIME allowlist.
- Filenames are basename-normalized, Unicode-normalized, and stripped of control characters.
- SQLAlchemy and bound SQL parameters prevent caller-controlled SQL composition.
- SHA-256 and uniqueness constraints prevent duplicate documents and transactions.
- Audit metadata redacts passwords, tokens, secrets, connection strings, and document content.
- MCP result counts are capped and direct contact fields are omitted from people searches.
- CORS requires an explicit approved origin configuration.

The API currently assumes a trusted local network. Before exposing it outside localhost, add an
OIDC reverse proxy or workload-identity gateway, TLS, rate limiting, and authorization policies.
Password hashing will be added only if native user authentication is introduced; plaintext
password storage is prohibited.

## Dependency checks

Run:

```bash
make lint
python -m pip audit
docker scout cves local://aari-data-platform-api
```

Image and Python dependency findings must be triaged before production promotion.

