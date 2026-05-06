# Architecture

## Runtime Shape

The container runs one FastAPI process.

That process exposes:

- `/healthz` for Container Apps health checks
- a background Telegram polling loop for command handling

## Components

### FastAPI App

- starts the bot loop on startup
- stops the bot loop on shutdown
- provides the health endpoint

### Telegram Polling Bot

- calls `getUpdates`
- parses `/ping`, `/status`, `/help`, `/brief`
- replies with `sendMessage`

### Azure OpenAI Client

- probes deployment availability
- sends `/brief` prompts to the configured Azure OpenAI deployment

### Blob Artifact Upload

- optionally writes `/brief` request-response artifacts to Blob Storage

## Azure Resources

- Resource Group
- Azure Container Registry
- Log Analytics Workspace
- Application Insights
- Azure Container Apps Environment
- Azure Container App
- Azure Key Vault
- Azure Storage Account

## Why Polling In V1

Polling is the simplest reliable option for a first Azure deployment:

- no public webhook registration flow
- no inbound Telegram validation complexity
- no extra abstraction layer

It is enough to validate bot behavior, container health, and Azure OpenAI integration.
