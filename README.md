# AARI Nexus Azure

AARI Nexus Operator rebuilt for Azure.

This repo deploys a simple Telegram bot backend to Azure Container Apps with:

- FastAPI runtime
- Telegram polling bot
- Azure OpenAI for `/brief`
- Azure Key Vault
- Azure Blob Storage for artifacts
- Log Analytics and Application Insights for observability
- Pulumi Python with Azure Native

V1 intentionally does not include AWS, Bedrock, Ollama, Kubernetes, or webhook complexity.

## Commands

- `/ping` -> `pong`
- `/help` -> command list
- `/status` -> Azure runtime status, model, region, version, uptime
- `/brief <prompt>` -> concise Azure OpenAI answer

## Health Endpoint

- `GET /healthz` returns `200`

## Repo Layout

```text
aari-nexus-azure/
├── app/
│   ├── main.py
│   ├── bot.py
│   ├── commands.py
│   ├── azure_openai_client.py
│   ├── config.py
│   └── telemetry.py
├── infra/
│   ├── Pulumi.yaml
│   ├── Pulumi.dev.yaml
│   ├── __main__.py
│   └── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
└── docs/
    ├── architecture.md
    ├── deployment.md
    └── runbook.md
```

## AWS Reference Findings

The AWS repo at `/Users/atlanta_ai_robotics/Projects/aari/aari-nexus` was used only as a behavioral reference.

What carried over:

- one small HTTP service process
- env-driven model selection
- simple command routing

What was removed:

- AWS deployment assumptions
- Bedrock integrations
- Ollama runtime
- local model routing

## Local Setup

1. Copy env file:

```bash
cp .env.example .env
```

2. Fill in:

- `TELEGRAM_BOT_TOKEN`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

3. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

4. Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Check health:

```bash
curl http://localhost:8000/healthz
```

## Local Docker Test

```bash
docker compose up --build
curl http://localhost:8000/healthz
```

## Azure Deployment Flow

Prereqs:

- Azure subscription
- Azure OpenAI access and deployment name
- Telegram bot token
- Pulumi account or local backend
- Azure CLI login

1. Login:

```bash
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
pulumi login
```

2. Build and push the container image to ACR after `pulumi preview` creates the registry name or by choosing a fixed tag:

```bash
cd infra
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
pulumi stack init dev
pulumi config set azure-native:location eastus
pulumi config set --secret telegramBotToken "<TOKEN>"
pulumi config set --secret azureOpenAiEndpoint "<ENDPOINT>"
pulumi config set --secret azureOpenAiApiKey "<API_KEY>"
pulumi config set --secret azureOpenAiDeployment "<DEPLOYMENT>"
pulumi config set --secret azureOpenAiApiVersion "2024-10-21"
pulumi preview
```

3. Build and push the app image to ACR using the exported login server:

```bash
az acr login --name <ACR_NAME>
docker build -t <ACR_LOGIN_SERVER>/aari-nexus-azure:dev ..
docker push <ACR_LOGIN_SERVER>/aari-nexus-azure:dev
```

4. Deploy:

```bash
pulumi up
```

5. Validate:

- browse `<container-app-url>/healthz`
- send `/ping` in Telegram
- send `/status`
- send `/help`
- send `/brief Explain AARI Nexus in one paragraph.`

## Notes

- polling is used instead of webhook for v1 simplicity
- Key Vault is created as the Azure secret store, while Pulumi secret config seeds the initial runtime values
- artifact uploads are optional and only activate when storage is configured

More detail:

- [docs/architecture.md](docs/architecture.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/runbook.md](docs/runbook.md)
