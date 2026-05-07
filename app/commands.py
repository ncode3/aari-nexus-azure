from __future__ import annotations

from datetime import UTC, datetime

from app.arbiter import NexusArbiter
from app.azure_openai_client import AzureOpenAIClient
from app.config import Settings
from app.telemetry import log_event, upload_artifact

ARBITER = NexusArbiter()


def build_help_text() -> str:
    return "\n".join(
        [
            "Available commands:",
            "/ping - connectivity test",
            "/status - runtime and Azure service status",
            "/help - show this message",
            "/brief <prompt> - send a concise request to Azure OpenAI",
            "",
            "Architecture notes:",
            "- command routing passes through the Nexus Arbiter",
            "- student intake and document flow are represented internally",
        ]
    )


async def handle_ping() -> str:
    return "pong"


async def handle_help() -> str:
    return build_help_text()


async def handle_status(
    settings: Settings,
    openai_client: AzureOpenAIClient,
    started_at: datetime,
) -> str:
    probe = await openai_client.probe()
    uptime = int((datetime.now(UTC) - started_at).total_seconds())
    services = {
        "openai": "healthy" if probe["healthy"] else f"error:{probe['status_code']}",
        "deployment": "present" if probe["deployment_found"] else "missing",
        "key_vault": "configured" if settings.azure_key_vault_uri else "not-configured",
        "blob_storage": "configured" if (settings.azure_storage_connection_string or settings.azure_storage_account_url) else "not-configured",
        "app_insights": "configured" if settings.app_insights_connection_string else "not-configured",
    }
    return "\n".join(
        [
            "AARI Nexus Azure status",
            f"azure_service_health: {services}",
            f"model_name: {settings.azure_openai_deployment}",
            f"region: {settings.azure_region}",
            f"app_version: {settings.app_version}",
            f"uptime_seconds: {uptime}",
        ]
    )


async def handle_brief(
    prompt: str,
    settings: Settings,
    openai_client: AzureOpenAIClient,
) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        return "Usage: /brief <prompt>"

    response = await openai_client.brief(cleaned)
    metadata = ARBITER.build_artifact_metadata(cleaned, response)
    log_event("telegram.brief", **metadata)
    await upload_artifact(
        settings,
        artifact_kind="briefs",
        filename="brief.json",
        payload={"artifact_type": "brief", **metadata},
    )
    return response
