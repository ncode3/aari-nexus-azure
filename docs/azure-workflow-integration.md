# Azure Workflow Integration

Azure jobs are HTTP clients, not database clients. They may stage a source file temporarily, then:

1. `POST /api/v1/documents` with the file, source system, source identifier, classification, and
   approved metadata.
2. Read the returned `ingestion_job_id`.
3. `GET /api/v1/ingestion/jobs/{id}` until `completed` or `failed`.
4. Retrieve document metadata with `GET /api/v1/documents/{id}`.

The provided adapter:

```bash
export AZURE_SUBMISSION_API_URL=https://private-aari-api.example
export AZURE_SUBMISSION_API_TOKEN=REDACTED
python scripts/submit_from_azure.py /tmp/staged.pdf \
  --source-system azure_document_workflow \
  --source-identifier "logic-app/run-id/blob-etag"
```

Use private connectivity, TLS, and workload identity at the gateway in production. The token
placeholder exists only for gateway compatibility and must not be committed. Azure receives no
PostgreSQL or MinIO credential. On successful submission, delete temporary Azure staging data
according to its retention policy only after checksum verification.

Existing Azure Blob assessment utilities remain available during migration. New production jobs
should call the API so PostgreSQL and MinIO remain authoritative.

