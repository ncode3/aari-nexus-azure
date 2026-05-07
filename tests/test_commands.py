from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime

from app.commands import handle_brief, handle_help, handle_ping, handle_status
from app.config import Settings


class FakeOpenAIClient:
    async def brief(self, prompt: str) -> str:
        return f"brief:{prompt}"

    async def probe(self) -> dict[str, object]:
        return {"healthy": True, "status_code": 200, "deployment_found": True}


BASE_SETTINGS = Settings(
    telegram_bot_token="token",
    azure_openai_endpoint="https://example.openai.azure.com",
    azure_openai_api_key="secret",
    azure_openai_deployment="gpt-4.1-mini",
    azure_openai_api_version="2024-10-21",
    azure_region="eastus",
    app_version="0.2.0",
    app_env="dev",
    bot_poll_interval_seconds=2,
    bot_allowed_chat_ids=set(),
    azure_storage_connection_string=None,
    azure_storage_account_url=None,
    azure_storage_container="artifacts",
    app_insights_connection_string="InstrumentationKey=test",
    azure_key_vault_uri="https://kv.vault.azure.net/",
)


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_ping(self) -> None:
        self.assertEqual(await handle_ping(), "pong")

    async def test_help(self) -> None:
        text = await handle_help()
        self.assertIn("/brief <prompt>", text)
        self.assertIn("Nexus Arbiter", text)

    async def test_status(self) -> None:
        status = await handle_status(BASE_SETTINGS, FakeOpenAIClient(), datetime.now(UTC))
        self.assertIn("AARI Nexus Azure status", status)
        self.assertIn("model_name: gpt-4.1-mini", status)

    async def test_brief_usage(self) -> None:
        self.assertEqual(await handle_brief("", BASE_SETTINGS, FakeOpenAIClient()), "Usage: /brief <prompt>")

    async def test_brief_response(self) -> None:
        settings = replace(BASE_SETTINGS, azure_storage_connection_string=None, azure_storage_account_url=None)
        result = await handle_brief("Explain AARI Nexus", settings, FakeOpenAIClient())
        self.assertEqual(result, "brief:Explain AARI Nexus")


if __name__ == "__main__":
    unittest.main()
