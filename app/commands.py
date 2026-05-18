from __future__ import annotations

import os
import json
import time
from datetime import UTC, datetime

from app.agents import ChiefOfStaffAgent, MemoryAgent, PartnershipAgent, classify_intent, make_action_package
from app.arbiter import NexusArbiter
from app.azure_openai_client import AzureOpenAIClient
from app.config import Settings
from app.memory import MemoryRecord, MemoryStore
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
            "/brief <topic> - retrieve memory and prepare an operational brief",
            "/followup <person/company/topic> - draft a follow-up action package for approval",
            "/prep <meeting/person/company> - prepare a meeting/person/company brief",
            "/remember <fact/decision> - save memory",
            "/find <topic/person/project> - search Nexus memory",
            "/draft <email/post/doc> - draft-only command, approval required before external use",
            "/task <task> - capture a task action package",
            "",
            "Architecture notes:",
            "- command routing passes through the Nexus Arbiter",
            "- context-heavy commands retrieve Nexus memory before answering",
            "- external execution requires approval",
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


def render_action_package(package: dict[str, object], debug_json: bool = False) -> str:
    if debug_json:
        return json.dumps(package, indent=2, sort_keys=True)

    lines = [
        f"Nexus: {package['answer']}",
        f"Agent: {package['agent']}",
    ]
    draft_output = str(package.get("draft_output") or "").strip()
    if draft_output:
        lines.extend(["", draft_output])

    next_step = str(package.get("recommended_next_step") or "").strip()
    if next_step:
        lines.extend(["", f"Next: {next_step}"])

    if package.get("approval_required"):
        options = ", ".join(package.get("approval_options", []))
        lines.extend(["", f"Approval required: {options}", f"Action ID: {package['id']}"])
    else:
        lines.extend(["", f"Stored: {package['id']}"])

    return "\n".join(lines)


def _infer_memory_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("person", "met ", "call with", "nolan", "student", "partner at")):
        return "people"
    if any(term in lowered for term in ("company", "organization", "foundation", "university", "college", "cisco", "microsoft", "nvidia")):
        return "organizations"
    if any(term in lowered for term in ("project", "workstream", "sprint", "build")):
        return "projects"
    if any(term in lowered for term in ("deadline", "due ", "by ", "before ")):
        return "deadlines"
    if any(term in lowered for term in ("task", "todo", "follow up")):
        return "tasks"
    return "decisions"


def _fallback_model_client(openai_client: AzureOpenAIClient):
    if hasattr(openai_client, "complete"):
        return openai_client

    class BriefOnlyAdapter:
        async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 450) -> str:
            return await openai_client.brief(f"{system_prompt}\n\n{user_prompt}")

    return BriefOnlyAdapter()


async def handle_operational_command(
    command: str,
    payload: str,
    settings: Settings,
    openai_client: AzureOpenAIClient,
    memory_store: MemoryStore,
) -> str:
    cleaned = payload.strip()
    if not cleaned:
        return f"Usage: {command} <topic or request>"

    routed = classify_intent(command, cleaned)
    original_command = f"{routed.command} {cleaned}".strip()

    context: list[MemoryRecord] = []
    if routed.command != "/remember":
        context = memory_store.search_memory(cleaned, limit=8)
        log_event("nexus.memory_retrieved", command=routed.command, agent=routed.agent, count=len(context))

    if routed.command == "/remember":
        record = memory_store.save_memory(cleaned, memory_type=_infer_memory_type(cleaned))
        agent = MemoryAgent()
        answer, draft, next_step = agent.remember(routed, record.id)
        context = [record]
    elif routed.command == "/find":
        agent = MemoryAgent()
        answer, draft, next_step = agent.find(routed, context)
    elif routed.command == "/prep":
        agent = ChiefOfStaffAgent()
        answer, draft, next_step = await agent.prep(_fallback_model_client(openai_client), routed, context)
    elif routed.command == "/followup":
        agent = PartnershipAgent()
        answer, draft, next_step = await agent.followup(_fallback_model_client(openai_client), routed, context)
    elif routed.command == "/brief":
        decision = ARBITER.preflight("/brief", cleaned)
        log_event("arbiter.preflight", **ARBITER.build_decision_log(decision))
        if decision.decision == "block":
            return decision.user_response or "Request blocked by policy."
        if decision.decision == "escalate":
            return decision.user_response or "This request requires review and approval."
        routed_payload = decision.safe_prompt if decision.decision == "modify" and decision.safe_prompt else cleaned
        agent = ChiefOfStaffAgent()
        routed = classify_intent("/brief", routed_payload)
        answer, draft, next_step = await agent.brief(_fallback_model_client(openai_client), routed, context)
        if decision.decision == "modify" and decision.user_response:
            answer = decision.user_response
    else:
        # MVP support for /draft and /task without external execution.
        answer = "Draft/task package prepared. Approval is required before external execution."
        draft = cleaned
        next_step = "Approve, edit, turn into a task, or cancel."

    package = make_action_package(
        routed=routed,
        original_command=original_command,
        context=context,
        answer=answer,
        draft_output=draft,
        recommended_next_step=next_step,
    )
    stored = memory_store.save_action_package(package)
    log_event(
        "nexus.action_package",
        action_id=stored["id"],
        command=routed.command,
        agent=routed.agent,
        intent=routed.intent,
        approval_required=bool(stored["approval_required"]),
        status=str(stored["status"]),
    )
    return render_action_package(stored, debug_json=settings.nexus_debug_json)


async def handle_brief(
    prompt: str,
    settings: Settings,
    openai_client: AzureOpenAIClient,
    memory_store: MemoryStore | None = None,
) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        return "Usage: /brief <topic or request>"

    if memory_store is not None:
        return await handle_operational_command("/brief", cleaned, settings, openai_client, memory_store)

    decision = ARBITER.preflight("/brief", cleaned)
    log_event("arbiter.preflight", **ARBITER.build_decision_log(decision))

    if decision.decision == "block":
        return decision.user_response or "Request blocked by policy."

    if decision.decision == "escalate":
        return decision.user_response or "This request requires review and approval."

    model_prompt = decision.safe_prompt if decision.decision == "modify" else cleaned
    response = await openai_client.brief(model_prompt)
    if decision.decision == "modify" and decision.user_response:
        response = f"{decision.user_response}\n\n{response}"

    metadata = ARBITER.build_artifact_metadata(cleaned, response)
    log_event("telegram.brief", **metadata)
    await upload_artifact(
        settings,
        artifact_kind="briefs",
        filename="brief.json",
        payload={"artifact_type": "brief", **metadata},
    )
    return response
