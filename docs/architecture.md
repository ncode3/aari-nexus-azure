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
- parses `/ping`, `/status`, `/help`, `/brief`, `/followup`, `/prep`, `/remember`, `/find`, `/draft`, `/task`
- replies with `sendMessage`

### Nexus Chief-Of-Staff Layer

- classifies command intent
- retrieves SQLite memory for context-heavy commands
- routes to MVP agents:
  - `ChiefOfStaffAgent`
  - `PartnershipAgent`
  - `GrantAgent`
  - `SprintAgent`
  - `InfrastructureAgent`
  - `MemoryAgent`
  - `WritingAgent`
- generates action packages
- stores full JSON packages in SQLite
- renders concise Telegram summaries
- marks external actions as approval-required instead of executing them

Commands that may draft external-facing work, such as `/followup`, `/draft`, and `/task`, produce pending action packages with `APPROVE`, `EDIT`, `TASK`, and `CANCEL` options. No external execution happens in this milestone.

### Azure OpenAI Client

- probes deployment availability
- sends operational drafting and briefing prompts to the configured Azure OpenAI deployment

### SQLite Memory

- local MVP storage, configured with `NEXUS_MEMORY_PATH`
- supports people, organizations, projects, decisions, tasks, deadlines, drafts, and action packages
- exposes `save_memory`, `search_memory`, `list_recent_memory`, `save_action_package`, `get_pending_action`, and `update_action_status`

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
