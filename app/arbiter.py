from __future__ import annotations

import hashlib
from dataclasses import dataclass


ALLOWED_COMMANDS = {"/ping", "/status", "/help", "/brief"}
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


@dataclass(frozen=True)
class CommandDecision:
    command: str
    prompt: str


class NexusArbiter:
    """
    Runtime policy layer for AARI Nexus Azure.

    It performs three real duties:
    - authorizes and normalizes bot commands
    - sanitizes user prompts before model dispatch
    - redacts sensitive fields from logs and artifact metadata
    """

    def authorize_command(self, command: str, remainder: str) -> CommandDecision:
        normalized = command.strip().lower()
        if normalized not in ALLOWED_COMMANDS:
            raise ValueError("Unknown command. Use /help.")
        return CommandDecision(command=normalized, prompt=self.sanitize_prompt(remainder))

    def sanitize_prompt(self, prompt: str) -> str:
        cleaned = " ".join((prompt or "").strip().split())
        return cleaned[:4000]

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

