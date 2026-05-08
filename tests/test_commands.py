from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime

from app.commands import handle_brief, handle_help, handle_ping, handle_status
from app.config import Settings


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.last_prompt: str | None = None

    async def brief(self, prompt: str) -> str:
        self.last_prompt = prompt
        return f"brief:{prompt}"

    async def probe(self) -> dict[str, object]:
        return {"healthy": True, "status_code": 200, "deployment_found": True}


class FakePepClient:
    async def health_check(self) -> dict[str, object]:
        return {"status": "healthy", "healthy": True, "base_url": "http://localhost:8081"}


class DegradedPepClient:
    async def health_check(self) -> dict[str, object]:
        return {"status": "degraded", "healthy": False, "base_url": "http://localhost:8081", "error": "ConnectTimeout"}


BASE_SETTINGS = Settings(
    telegram_bot_token="token",
    azure_openai_endpoint="https://example.openai.azure.com",
    azure_openai_api_key="secret",
    azure_openai_deployment="gpt-4.1-mini",
    azure_openai_api_version="2024-10-21",
    azure_region="eastus",
    app_version="0.2.2",
    app_env="dev",
    bot_poll_interval_seconds=2,
    bot_allowed_chat_ids=set(),
    azure_storage_connection_string=None,
    azure_storage_account_url=None,
    azure_storage_container="artifacts",
    app_insights_connection_string="InstrumentationKey=test",
    azure_key_vault_uri="https://kv.vault.azure.net/",
    pep_base_url="http://localhost:8081",
    pep_health_timeout_seconds=1.0,
    model_timeout_seconds=20.0,
)


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_ping(self) -> None:
        text = await handle_ping(BASE_SETTINGS, 0.0)
        self.assertIn("pong", text)
        self.assertIn("latency_ms:", text)
        self.assertIn("bot_pid:", text)
        self.assertIn("app_version: 0.2.2", text)

    async def test_help(self) -> None:
        text = await handle_help()
        self.assertIn("/brief <prompt>", text)
        self.assertIn("Nexus Arbiter", text)

    async def test_status(self) -> None:
        status, services = await handle_status(BASE_SETTINGS, FakeOpenAIClient(), FakePepClient(), datetime.now(UTC))
        self.assertIn("AARI Nexus Azure status", status)
        self.assertIn("model_name: gpt-4.1-mini", status)
        self.assertIn("pep_base_url: http://localhost:8081", status)
        self.assertEqual(services["pep"], "healthy")

    async def test_status_pep_degraded(self) -> None:
        status, services = await handle_status(BASE_SETTINGS, FakeOpenAIClient(), DegradedPepClient(), datetime.now(UTC))
        self.assertIn("'pep': 'degraded'", status)
        self.assertEqual(services["pep"], "degraded")

    async def test_brief_usage(self) -> None:
        self.assertEqual(await handle_brief("", BASE_SETTINGS, FakeOpenAIClient()), "Usage: /brief <topic or request>")

    async def test_brief_response(self) -> None:
        settings = replace(BASE_SETTINGS, azure_storage_connection_string=None, azure_storage_account_url=None)
        client = FakeOpenAIClient()
        result = await handle_brief("Explain AARI Nexus", settings, client)
        self.assertEqual(result, "brief:Explain AARI Nexus")
        self.assertEqual(client.last_prompt, "Explain AARI Nexus")

    async def test_brief_refuses_binding_commitment(self) -> None:
        client = FakeOpenAIClient()
        result = await handle_brief(
            "Draft a message committing AARI to a $100,000 contract with Microsoft",
            BASE_SETTINGS,
            client,
        )
        self.assertIn("cannot authorize or imply", result)
        self.assertIn("for discussion only", result)
        self.assertIn("subject to review and approval", result)
        self.assertIsNone(client.last_prompt)

    async def test_brief_allows_partner_discussion(self) -> None:
        client = FakeOpenAIClient()
        result = await handle_brief("Draft a follow-up asking Microsoft to discuss possible sponsorship", BASE_SETTINGS, client)
        self.assertEqual(result, "brief:Draft a follow-up asking Microsoft to discuss possible sponsorship")
        self.assertIsNotNone(client.last_prompt)
        self.assertEqual(client.last_prompt, "Draft a follow-up asking Microsoft to discuss possible sponsorship")

    async def test_brief_rewrites_guarantee_language(self) -> None:
        client = FakeOpenAIClient()
        result = await handle_brief("Write a message saying AARI guarantees 50 internships", BASE_SETTINGS, client)
        self.assertIn("cannot authorize or imply", result)
        self.assertIn("for discussion only", result)
        self.assertIsNotNone(client.last_prompt)

    async def test_brief_escalates_grant_acceptance(self) -> None:
        client = FakeOpenAIClient()
        result = await handle_brief("Draft a note accepting Cisco grant terms", BASE_SETTINGS, client)
        self.assertIn("requires review and approval", result)
        self.assertIsNone(client.last_prompt)


if __name__ == "__main__":
    unittest.main()
