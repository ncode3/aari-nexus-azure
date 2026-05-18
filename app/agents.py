from __future__ import annotations

import textwrap
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from app.memory import MemoryRecord


class ModelClient(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 450) -> str:
        ...


AGENT_BY_COMMAND = {
    "/brief": "ChiefOfStaffAgent",
    "/followup": "PartnershipAgent",
    "/prep": "ChiefOfStaffAgent",
    "/draft": "WritingAgent",
    "/remember": "MemoryAgent",
    "/find": "MemoryAgent",
    "/task": "SprintAgent",
    "/status": "InfrastructureAgent",
}


INTENT_BY_COMMAND = {
    "/brief": "operational_brief",
    "/followup": "follow_up_draft",
    "/prep": "meeting_prep",
    "/draft": "draft_generation",
    "/remember": "memory_capture",
    "/find": "memory_search",
    "/task": "task_capture",
    "/status": "runtime_status",
}


APPROVAL_REQUIRED = {"/followup", "/draft", "/task"}


@dataclass(frozen=True)
class RoutedCommand:
    command: str
    payload: str
    agent: str
    intent: str


def classify_intent(command: str, payload: str) -> RoutedCommand:
    normalized = command.strip().lower()
    if normalized not in AGENT_BY_COMMAND:
        normalized = "/brief"
    lowered = payload.lower()
    agent = AGENT_BY_COMMAND[normalized]
    if normalized == "/brief":
        if any(term in lowered for term in ("grant", "funder", "foundation", "philanthropy")):
            agent = "GrantAgent"
        elif any(term in lowered for term in ("azure", "pulumi", "infrastructure", "container", "cost", "security")):
            agent = "InfrastructureAgent"
        elif any(term in lowered for term in ("partner", "sponsor", "microsoft", "cisco", "nvidia", "qts", "google")):
            agent = "PartnershipAgent"
    return RoutedCommand(
        command=normalized,
        payload=payload.strip(),
        agent=agent,
        intent=INTENT_BY_COMMAND.get(normalized, "operational_request"),
    )


def context_to_lines(records: list[MemoryRecord]) -> list[str]:
    return [f"{record.type}: {record.content}" for record in records]


def context_summary(records: list[MemoryRecord]) -> str:
    lines = context_to_lines(records)
    if not lines:
        return "No relevant memory found."
    return "\n".join(f"- {line}" for line in lines)


def make_action_package(
    *,
    routed: RoutedCommand,
    original_command: str,
    context: list[MemoryRecord],
    answer: str,
    draft_output: str,
    recommended_next_step: str,
    approval_required: bool | None = None,
) -> dict[str, Any]:
    needs_approval = routed.command in APPROVAL_REQUIRED if approval_required is None else approval_required
    return {
        "id": f"act_{uuid.uuid4().hex[:12]}",
        "created_at": datetime.now(UTC).isoformat(),
        "command": original_command.strip(),
        "agent": routed.agent,
        "intent": routed.intent,
        "context_used": context_to_lines(context),
        "answer": answer.strip(),
        "draft_output": draft_output.strip(),
        "recommended_next_step": recommended_next_step.strip(),
        "approval_required": needs_approval,
        "approval_options": ["APPROVE", "EDIT", "TASK", "CANCEL"] if needs_approval else [],
        "status": "pending" if needs_approval else "stored",
    }


class ChiefOfStaffAgent:
    system_prompt = (
        "You are AARI Nexus, Nolan's private AI chief of staff. "
        "Use retrieved memory first. Produce concise operational output, not chatbot filler. "
        "Do not claim you executed external actions."
    )

    async def brief(self, model: ModelClient, routed: RoutedCommand, context: list[MemoryRecord]) -> tuple[str, str, str]:
        user_prompt = textwrap.dedent(
            f"""
            Request: {routed.payload}

            Retrieved memory:
            {context_summary(context)}

            Return:
            1. A short answer.
            2. A practical brief with bullets.
            3. One recommended next step.
            """
        ).strip()
        draft = await model.complete(self.system_prompt, user_prompt)
        answer = "Brief prepared from retrieved Nexus memory and current request."
        next_step = "Review the brief and decide whether to turn any item into a task or external follow-up."
        return answer, draft, next_step

    async def prep(self, model: ModelClient, routed: RoutedCommand, context: list[MemoryRecord]) -> tuple[str, str, str]:
        user_prompt = textwrap.dedent(
            f"""
            Prep target: {routed.payload}

            Retrieved memory:
            {context_summary(context)}

            Create a meeting prep package:
            - what matters
            - likely objectives
            - risks or sensitivities
            - smart questions Nolan should ask
            - recommended opening position
            """
        ).strip()
        draft = await model.complete(self.system_prompt, user_prompt)
        answer = "Prep package ready."
        next_step = "Use this prep before the meeting; ask Nexus for a follow-up draft afterward if needed."
        return answer, draft, next_step


class PartnershipAgent:
    system_prompt = (
        "You are AARI Nexus PartnershipAgent. Draft partner follow-ups for Nolan. "
        "Keep language strategic, non-binding, and subject to approval. "
        "Never commit AARI to money, legal terms, hiring guarantees, or external messages."
    )

    async def followup(self, model: ModelClient, routed: RoutedCommand, context: list[MemoryRecord]) -> tuple[str, str, str]:
        user_prompt = textwrap.dedent(
            f"""
            Follow-up target/topic: {routed.payload}

            Retrieved memory:
            {context_summary(context)}

            Draft a concise follow-up message Nolan could send.
            Include a clear ask and keep it non-binding.
            """
        ).strip()
        draft = await model.complete(self.system_prompt, user_prompt)
        answer = "Follow-up draft prepared. Approval is required before any external send."
        next_step = "Approve, edit, turn into a task, or cancel before sending externally."
        return answer, draft, next_step


class MemoryAgent:
    def remember(self, routed: RoutedCommand, saved_id: str) -> tuple[str, str, str]:
        answer = f"Remembered: {routed.payload}"
        draft = f"Saved memory record: {saved_id}"
        next_step = "Use /find, /brief, /prep, or /followup to retrieve this later."
        return answer, draft, next_step

    def find(self, routed: RoutedCommand, context: list[MemoryRecord]) -> tuple[str, str, str]:
        if not context:
            return "No matching Nexus memory found.", "", "Add context with /remember if this should be tracked."
        lines = "\n".join(f"- {record.type}: {record.content}" for record in context)
        return f"Found {len(context)} matching memory item(s).", lines, "Use /prep or /followup with this topic if you want an action package."


class WritingAgent:
    pass


class GrantAgent:
    pass


class SprintAgent:
    pass


class InfrastructureAgent:
    pass
