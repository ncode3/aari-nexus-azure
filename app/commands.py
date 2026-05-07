from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from app.arbiter import NexusArbiter
from app.azure_openai_client import AzureOpenAIClient
from app.config import Settings
from app.pep_client import PepClient
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


async def handle_ping(
    settings: Settings,
    command_started: float,
) -> str:
    latency_ms = max(0, round((time.perf_counter() - command_started) * 1000, 2))
    return "\n".join(
        [
            "pong",
            f"latency_ms: {latency_ms}",
            f"bot_pid: {os.getpid()}",
            f"app_version: {settings.app_version}",
        ]
    )


async def handle_help() -> str:
    return build_help_text()


async def handle_status(
    settings: Settings,
    openai_client: AzureOpenAIClient,
    pep_client: PepClient,
    started_at: datetime,
) -> tuple[str, dict[str, str]]:
    probe = await openai_client.probe()
    pep_status = await pep_client.health_check()
    uptime = int((datetime.now(UTC) - started_at).total_seconds())
    services = {
        "openai": "healthy" if probe["healthy"] else f"error:{probe['status_code']}",
        "deployment": "present" if probe["deployment_found"] else "missing",
        "key_vault": "configured" if settings.azure_key_vault_uri else "not-configured",
        "blob_storage": "configured" if (settings.azure_storage_connection_string or settings.azure_storage_account_url) else "not-configured",
        "app_insights": "configured" if settings.app_insights_connection_string else "not-configured",
        "pep": pep_status["status"],
    }
    return "\n".join(
        [
            "AARI Nexus Azure status",
            f"azure_service_health: {services}",
            f"pep_base_url: {pep_status['base_url']}",
            f"model_name: {settings.azure_openai_deployment}",
            f"region: {settings.azure_region}",
            f"app_version: {settings.app_version}",
            f"uptime_seconds: {uptime}",
        ]
    ), services


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
