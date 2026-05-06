# Deployment

## 1. Azure Login

```bash
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
pulumi login
```

## 2. Configure Pulumi

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

## 3. Build And Push Image

After the registry exists or after choosing the registry name:

```bash
az acr login --name <ACR_NAME>
docker build -t <ACR_LOGIN_SERVER>/aari-nexus-azure:dev ..
docker push <ACR_LOGIN_SERVER>/aari-nexus-azure:dev
```

## 4. Deploy

```bash
pulumi up
```

## 5. Validate

```bash
curl https://<CONTAINER_APP_FQDN>/healthz
```

Then test in Telegram:

- `/ping`
- `/status`
- `/help`
- `/brief Explain AARI Nexus in one paragraph.`
