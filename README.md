# AARI Nexus Azure

AARI Nexus Operator rebuilt for Azure.

This repo deploys a private AARI Nexus Telegram backend to Azure Container Apps with:

- FastAPI runtime
- Telegram polling bot
- Azure OpenAI for operational drafting and briefs
- SQLite memory and action packages for the MVP chief-of-staff workflow
- Azure Key Vault
- Azure Blob Storage for artifacts
- Log Analytics and Application Insights for observability
- an Arbiter layer for command authorization and log redaction
- Pulumi Python with Azure Native

V1 intentionally does not include AWS, Bedrock, Ollama, Kubernetes, or webhook complexity.

## Commands

- `/ping` -> bot-only liveness check with `pong`, `latency_ms`, `bot_pid`, `app_version`
- `/help` -> command list
- `/status` -> Azure runtime status, model, region, version, uptime, and degraded dependency checks
- `/brief <topic>` -> retrieve memory and prepare an operational brief
- `/followup <person/company/topic>` -> retrieve context, draft a follow-up, store a pending action package
- `/prep <meeting/person/company>` -> retrieve context and prepare a meeting/person/company brief
- `/remember <fact/decision>` -> save memory
- `/find <topic/person/project>` -> search memory
- `/draft <email/post/doc>` -> store a draft action package requiring approval before external use
- `/task <task>` -> capture a task action package

Nexus stores full JSON action packages in SQLite. Telegram output stays concise unless `NEXUS_DEBUG_JSON=true`.

## Chief-Of-Staff Workflow

The operational command path is:

1. Receive Telegram message
2. Classify command intent
3. Retrieve relevant memory for context-heavy commands
4. Route to the correct MVP agent
5. Generate an action package
6. Store the package
7. Ask Nolan for approval when external execution would be required

External execution is intentionally not implemented in this milestone. Nexus may draft, summarize, remember, prepare, and recommend. It must not send email, deploy infrastructure, delete data, spend money, or message external people without approval.

MVP agents:

- `ChiefOfStaffAgent`
- `PartnershipAgent`
- `GrantAgent`
- `SprintAgent`
- `InfrastructureAgent`
- `MemoryAgent`
- `WritingAgent`

SQLite memory currently supports:

- people
- organizations
- projects
- decisions
- tasks
- deadlines
- drafts
- action packages

## Health Endpoint

- `GET /healthz` returns `200`

## Repo Layout

```text
aari-nexus-azure/
├── app/
│   ├── arbiter.py
│   ├── document_flow.py
│   ├── intake.py
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
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   └── runbook.md
└── tests/
    ├── test_arbiter.py
    └── test_commands.py
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
- `PEP_BASE_URL`
- `NEXUS_MEMORY_PATH`
- `NEXUS_DEBUG_JSON`
- optional production-only values:
  - `AZURE_KEY_VAULT_URI`
  - `AZURE_CLIENT_ID`

PEP URL rules:

- local single-process testing uses `http://localhost:8081`
- Docker Compose uses `http://pep:8081`
- Azure Container Apps uses the internal service URL for the PEP app
- never use `0.0.0.0` as a client URL

3. Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

4. Run tests:

```bash
python3 -m unittest discover -s tests
```

5. Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

6. Check health:

```bash
curl http://localhost:8000/healthz
```

7. Expected `/ping` behavior:

- returns immediately without calling PEP, Azure OpenAI, Blob Storage, Key Vault, or Application Insights
- includes `latency_ms`, `bot_pid`, and `app_version`

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
pulumi config set environment dev
pulumi config set regionAbbr eus
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
- send `/remember Cisco is interested in AARI edge AI workforce programming`
- send `/find Cisco edge AI`
- send `/brief Cisco partnership context`
- send `/prep QTS data center workforce meeting`
- send `/followup Microsoft partnership`

## Notes

- polling is used instead of webhook for v1 simplicity
- Key Vault is the production secret source for the Container App
- the app resolves production secrets from Key Vault at startup by using `DefaultAzureCredential` with the user-assigned managed identity
- the Container App uses managed identity for ACR pull, Key Vault secret reads, and Blob artifact writes
- PEP health checks use `PEP_BASE_URL` with a 1-second timeout and degrade `/status` instead of blocking the bot
- `/ping` is isolated from downstream dependencies and serves as a bot-only liveness check
- action packages are stored in SQLite locally for the MVP
- Telegram replies render human-readable summaries, not raw JSON, unless `NEXUS_DEBUG_JSON=true`
- artifact uploads store sanitized metadata, not raw prompts or responses

More detail:

- [docs/architecture.md](docs/architecture.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/runbook.md](docs/runbook.md)
