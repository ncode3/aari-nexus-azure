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

### Arbiter Layer

- authorizes supported commands before execution
- sanitizes `/brief` prompts before model dispatch
- redacts sensitive log fields and artifact metadata

### Telegram Polling Bot

- calls `getUpdates`
- parses `/ping`, `/status`, `/help`, `/brief`
- replies with `sendMessage`

### Azure OpenAI Client

- probes deployment availability
- sends `/brief` prompts to the configured Azure OpenAI deployment

### Blob Artifact Upload

- optionally writes sanitized `/brief` metadata artifacts to Blob Storage

### Student Intake And Document Flow

- `app/intake.py` represents student intake records and document classification
- `app/document_flow.py` summarizes resume and supporting document flow without logging document contents

## Azure Resources

- Resource Group
- User Assigned Managed Identity
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
