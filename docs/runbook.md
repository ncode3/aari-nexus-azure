# Runbook

## Health Check

```bash
curl http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok","service":"aari-nexus-azure","version":"0.1.0","region":"eastus"}
```

## Common Runtime Checks

### Bot does not answer

Check:

- `TELEGRAM_BOT_TOKEN`
- container logs
- bot polling loop startup logs

### `/brief` fails

Check:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

### `/status` reports deployment missing

The endpoint is reachable, but the configured deployment name does not match a live Azure OpenAI deployment.

### Artifact uploads do not appear

Check:

- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER`

## Container App Logs

Use Azure Container Apps log streaming or Azure Monitor logs after deployment.
