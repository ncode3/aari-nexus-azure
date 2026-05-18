from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal


ALLOWED_COMMANDS = {
    "/ping",
    "/status",
    "/help",
    "/brief",
    "/followup",
    "/prep",
    "/draft",
    "/remember",
    "/find",
    "/task",
}
GENERATIVE_COMMANDS = {"/brief", "/followup", "/prep", "/draft", "/task"}
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "telegram_bot_token",
    "token",
    "prompt",
    "response",
    "resume_text",
    "document_text",
    "chat_id",
}

PolicyDecisionType = Literal["allow", "modify", "block", "escalate"]
RiskLevel = Literal["low", "elevated"]
PolicyCategory = Literal[
    "none",
    "financial_commitment",
    "legal_commitment",
    "contract_language",
    "authority_claim",
    "external_partner_commitment",
    "grant_or_funder_promise",
    "employment_or_offer_commitment",
]

FINANCIAL_MARKERS = ("$", "payment", "purchase", "invoice", "budget approval", "100,000", "50000", "50,000")
LEGAL_MARKERS = ("legal commitment", "binding", "obligate", "obligation")
CONTRACT_MARKERS = ("contract", "agreement", "agree to", "sign", "execute", "terms", "msa", "sow", "accept terms")
AUTHORITY_MARKERS = ("authorize", "approved by aari", "on behalf of aari", "guarantee", "guarantees", "commit", "committing")
PARTNER_NAMES = ("microsoft", "aws", "nvidia", "cisco", "google", "ibm", "salesforce", "qts", "siemens")
GRANT_MARKERS = ("grant", "funder", "sponsor", "sponsorship", "promise funding", "grant terms")
EMPLOYMENT_MARKERS = ("offer letter", "employment offer", "internship guarantee", "hire", "employment terms", "50 internships")


@dataclass(frozen=True)
class CommandDecision:
    command: str
    prompt: str


@dataclass(frozen=True)
class PreflightDecision:
    command: str
    risk_level: RiskLevel
    policy_category: PolicyCategory
    decision: PolicyDecisionType
    reason: str
    prompt: str
    safe_prompt: str | None
    user_response: str | None
    model_called: bool


class NexusArbiter:
    """
    Runtime policy layer for AARI Nexus Azure.

    It performs real duties:
    - authorizes and normalizes bot commands
    - classifies high-risk generative prompts before model dispatch
    - sanitizes user prompts before model dispatch
    - redacts sensitive fields from logs and artifact metadata
    """

    def authorize_command(self, command: str, remainder: str) -> CommandDecision:
        normalized = command.strip().lower()
        if normalized not in ALLOWED_COMMANDS:
            raise ValueError("Unknown command. Use /help.")
        return CommandDecision(command=normalized, prompt=self.sanitize_prompt(remainder))

    def preflight(self, command: str, prompt: str) -> PreflightDecision:
        cleaned = self.sanitize_prompt(prompt)
        if command not in GENERATIVE_COMMANDS:
            return PreflightDecision(
                command=command,
                risk_level="low",
                policy_category="none",
                decision="allow",
                reason="non-generative command",
                prompt=cleaned,
                safe_prompt=None,
                user_response=None,
                model_called=False,
            )

        category = self.classify_policy_category(cleaned)
        if category == "none":
            return PreflightDecision(
                command=command,
                risk_level="low",
                policy_category="none",
                decision="allow",
                reason="no elevated-risk language detected",
                prompt=cleaned,
                safe_prompt=cleaned,
                user_response=None,
                model_called=True,
            )

        safe_prompt = self.build_safe_prompt(cleaned)
        decision: PolicyDecisionType = "modify"
        if category in {"legal_commitment", "contract_language"}:
            decision = "escalate"

        return PreflightDecision(
            command=command,
            risk_level="elevated",
            policy_category=category,
            decision=decision,
            reason="binding or commitment language detected",
            prompt=cleaned,
            safe_prompt=safe_prompt,
            user_response=self.build_user_response(category, decision),
            model_called=decision in {"allow", "modify"},
        )

    def classify_policy_category(self, prompt: str) -> PolicyCategory:
        lowered = prompt.lower()

        if any(marker in lowered for marker in LEGAL_MARKERS):
            return "legal_commitment"
        if any(marker in lowered for marker in CONTRACT_MARKERS):
            return "contract_language"
        if any(marker in lowered for marker in FINANCIAL_MARKERS):
            return "financial_commitment"
        if any(marker in lowered for marker in EMPLOYMENT_MARKERS):
            return "employment_or_offer_commitment"
        if any(marker in lowered for marker in GRANT_MARKERS) and any(
            trigger in lowered for trigger in ("accept", "agree", "commit", "guarantee", "promise")
        ):
            return "grant_or_funder_promise"
        if any(name in lowered for name in PARTNER_NAMES) and any(
            trigger in lowered for trigger in ("commit", "contract", "agree", "accept", "sign", "guarantee", "$")
        ):
            return "external_partner_commitment"
        if any(marker in lowered for marker in AUTHORITY_MARKERS):
            return "authority_claim"
        return "none"

    def sanitize_prompt(self, prompt: str) -> str:
        cleaned = " ".join((prompt or "").strip().split())
        return cleaned[:4000]

    def build_safe_prompt(self, prompt: str) -> str:
        return (
            "Draft non-binding language for discussion only. "
            "Do not authorize, imply, or accept any financial, legal, employment, grant, or partner commitment. "
            "Clearly mark the draft as subject to review and approval. "
            f"User request: {prompt}"
        )

    def build_user_response(self, category: PolicyCategory, decision: PolicyDecisionType) -> str:
        base = (
            "I can draft non-binding language for review, but I cannot authorize or imply a financial or contractual "
            "commitment on behalf of AARI."
        )
        if decision == "escalate":
            return (
                f"{base} This request touches {category.replace('_', ' ')} and requires review and approval before any "
                "binding language is used. I can provide a for discussion only draft subject to review and approval."
            )
        return (
            f"{base} I will provide a for discussion only draft subject to review and approval instead of binding "
            f"language because this request touches {category.replace('_', ' ')}."
        )

    def redact_fields(self, fields: dict[str, object]) -> dict[str, object]:
        redacted: dict[str, object] = {}
        for key, value in fields.items():
            normalized = key.lower()
            if normalized in SENSITIVE_KEYS:
                redacted[key] = "[redacted]"
            elif normalized.endswith("_id") and value is not None:
                redacted[key] = self.hash_identifier(str(value))
            else:
                redacted[key] = value
        return redacted

    def hash_identifier(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    def build_artifact_metadata(self, prompt: str, response: str) -> dict[str, object]:
        return {
            "prompt_hash": self.hash_identifier(prompt),
            "prompt_length": len(prompt),
            "response_hash": self.hash_identifier(response),
            "response_length": len(response),
        }

    def build_decision_log(self, decision: PreflightDecision) -> dict[str, object]:
        return {
            "command": decision.command,
            "risk_level": decision.risk_level,
            "policy_category": decision.policy_category,
            "decision": decision.decision,
            "reason": decision.reason,
            "timestamp": datetime.now(UTC).isoformat(),
            "model_called": decision.model_called,
        }
