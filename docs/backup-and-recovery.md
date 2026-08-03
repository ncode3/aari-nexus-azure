# Backup and Recovery

The backup contains a PostgreSQL custom-format dump and mirrors of both private MinIO buckets.
Store it encrypted and access-controlled; it can contain restricted records.

```bash
set -a
. ./.env
set +a
./scripts/backup.sh
```

Restore into an empty recovery environment first:

```bash
./scripts/restore.sh backups/20260731T120000Z
python scripts/verify_environment.py
```

PostgreSQL uses `pg_dump` and `pg_restore`; MinIO uses the standard `mc mirror` S3-compatible
workflow. A recovery drill is successful only when:

1. Alembic reports the expected head.
2. Table and object counts match the backup manifest.
3. A sample object SHA-256 matches.
4. API readiness and representative student/cohort queries pass.
5. The restored read-only role cannot mutate a table.

Run a restore drill quarterly and after material schema changes. Docker volumes persist through
container restarts and `docker compose down`; `docker compose down --volumes` destroys local data
and is prohibited outside an explicitly approved disposable test environment.

