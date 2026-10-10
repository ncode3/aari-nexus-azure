"""Opt-in local Ollama inference adapter.

This module does not expose an HTTP endpoint, change model routing, or connect
Azure to a laptop. Callers must establish an authenticated private transport
before using a remote host. Default: loopback only.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

import httpx


def validate_ollama_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise ValueError("Ollama pilot accepts only loopback HTTP")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Ollama must be bound to loopback; no public or LAN endpoints")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Ollama URL must contain only scheme, host and port")
    if parsed.port is None:
        raise ValueError("Specify the Ollama port explicitly")
    return base_url.rstrip("/")


class OllamaLocalClient:
    """Implements the existing brief/complete/probe model-client contract."""

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434",
                 timeout_seconds: float = 30.0) -> None:
        if not model.strip():
            raise ValueError("An explicit local model name is required")
        self.model = model
        self.base_url = validate_ollama_url(base_url)
        self.timeout_seconds = timeout_seconds

    async def brief(self, prompt: str) -> str:
        return await self.complete(
            "You are AARI Nexus Operator. Give concise, direct answers with no fluff.",
            prompt,
            max_tokens=300,
        )

    async def complete(self, system_prompt: str, user_prompt: str,
                       max_tokens: int = 450) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        answer = data.get("message", {}).get("content")
        if not isinstance(answer, str):
            raise ValueError("Ollama response did not contain message.content")
        return answer

    async def probe(self) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
            found = any(item.get("name") == self.model or
                        item.get("model") == self.model for item in models)
            return {"healthy": found, "deployment_found": found,
                    "status_code": 200 if found else 404}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return {"healthy": False, "deployment_found": False, "status_code": 503}
