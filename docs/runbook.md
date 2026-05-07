# Runbook

## Health Check

```bash
curl http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok","service":"aari-nexus-azure","version":"0.2.2","region":"eastus"}
```

## Common Runtime Checks

### Bot does not answer

Check:

- `TELEGRAM_BOT_TOKEN`
- container logs
- bot polling loop startup logs

### `/ping` is slow

`/ping` should not depend on PEP or Azure OpenAI. If it slows down, check bot logs for command latency and verify no dependency checks were added back into the `/ping` path.

### `/brief` fails

Check:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- Key Vault secret references are resolving in Container Apps
- the managed identity has Key Vault Secrets User and Blob Data Contributor access

### `/status` reports deployment missing

The endpoint is reachable, but the configured deployment name does not match a live Azure OpenAI deployment.

### `/status` reports `pep: degraded`

Check:

- `PEP_BASE_URL`
- local single-process value: `http://localhost:8081`
- Docker Compose value: `http://pep:8081`
- Azure internal service URL for Container Apps
- do not use `0.0.0.0` as a client URL
- PEP health timeout is intentionally capped at 1 second

### Artifact uploads do not appear

Check:

- `AZURE_STORAGE_ACCOUNT_URL` or `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER`
- the managed identity has Storage Blob Data Contributor on the storage account

## Container App Logs

Use Azure Container Apps log streaming or Azure Monitor logs after deployment.
