from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from tempfile import TemporaryDirectory

from app.commands import handle_brief, handle_help, handle_operational_command, handle_ping, handle_status
from app.config import Settings
from app.memory import MemoryStore


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.last_prompt: str | None = None

    async def brief(self, prompt: str) -> str:
        self.last_prompt = prompt
        return f"brief:{prompt}"

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 450) -> str:
        self.last_prompt = user_prompt
        return f"complete:{user_prompt[:80]}"

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
    nexus_memory_path="data/test_memory.sqlite3",
    nexus_debug_json=False,
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
        self.assertIn("/brief <topic>", text)
        self.assertIn("/remember <fact/decision>", text)
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

    async def test_remember_and_find(self) -> None:
        with TemporaryDirectory() as tmp:
            store = MemoryStore(f"{tmp}/memory.sqlite3")
            result = await handle_operational_command(
                "/remember",
                "Cisco is interested in AARI edge AI workforce programming",
                BASE_SETTINGS,
                FakeOpenAIClient(),
                store,
            )
            self.assertIn("Remembered", result)
            result = await handle_operational_command("/find", "Cisco edge AI", BASE_SETTINGS, FakeOpenAIClient(), store)
            self.assertIn("Found 1 matching memory", result)
            self.assertIn("Cisco is interested", result)

    async def test_followup_stores_pending_action_package(self) -> None:
        with TemporaryDirectory() as tmp:
            store = MemoryStore(f"{tmp}/memory.sqlite3")
            store.save_memory("Microsoft asked for an AARI partnership summary", "organizations")
            result = await handle_operational_command(
                "/followup",
                "Microsoft partnership",
                BASE_SETTINGS,
                FakeOpenAIClient(),
                store,
            )
            self.assertIn("Approval required: APPROVE, EDIT, TASK, CANCEL", result)
            pending = store.get_pending_action()
            self.assertIsNotNone(pending)
            assert pending is not None
            self.assertEqual(pending["agent"], "PartnershipAgent")
            self.assertEqual(pending["status"], "pending")
            self.assertTrue(pending["approval_required"])

    async def test_prep_retrieves_memory_before_answering(self) -> None:
        with TemporaryDirectory() as tmp:
            store = MemoryStore(f"{tmp}/memory.sqlite3")
            client = FakeOpenAIClient()
            store.save_memory("QTS discussion centered on data center workforce curriculum", "organizations")
            result = await handle_operational_command("/prep", "QTS", BASE_SETTINGS, client, store)
            self.assertIn("Prep package ready", result)
            self.assertIsNotNone(client.last_prompt)
            assert client.last_prompt is not None
            self.assertIn("QTS discussion centered", client.last_prompt)


if __name__ == "__main__":
    unittest.main()
