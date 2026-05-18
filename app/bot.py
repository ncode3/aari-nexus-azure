from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

import httpx

from app.arbiter import NexusArbiter
from app.azure_openai_client import AzureOpenAIClient
from app.commands import handle_brief, handle_help, handle_operational_command, handle_ping, handle_status
from app.config import Settings
from app.memory import MemoryStore
from app.pep_client import PepClient
from app.telemetry import log_event


class TelegramBotRunner:
    def __init__(
        self,
        settings: Settings,
        openai_client: AzureOpenAIClient,
        pep_client: PepClient,
        started_at: datetime,
    ) -> None:
        self.settings = settings
        self.openai_client = openai_client
        self.pep_client = pep_client
        self.started_at = started_at
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._offset = 0
        self._logger = logging.getLogger("aari-nexus-azure.bot")
        self._arbiter = NexusArbiter()
        self.memory_store = MemoryStore(settings.nexus_memory_path)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def _poll_loop(self) -> None:
        async with httpx.AsyncClient(timeout=35) as client:
            while not self._stop_event.is_set():
                try:
                    payload = {
                        "timeout": 30,
                        "offset": self._offset,
                        "allowed_updates": ["message"],
                    }
                    response = await client.get(f"{self.base_url}/getUpdates", params=payload)
                    response.raise_for_status()
                    body = response.json()
                    for update in body.get("result", []):
                        self._offset = update["update_id"] + 1
                        await self._handle_update(client, update)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._logger.error("Polling loop error: %s", type(exc).__name__)
                    await asyncio.sleep(self.settings.bot_poll_interval_seconds)

    async def _handle_update(self, client: httpx.AsyncClient, update: dict[str, object]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            return

        if self.settings.bot_allowed_chat_ids and int(chat_id) not in self.settings.bot_allowed_chat_ids:
            await self._send_message(client, int(chat_id), "Unauthorized chat.")
            return

        command, _, remainder = text.partition(" ")
        command_started = time.perf_counter()
        try:
            decision = self._arbiter.authorize_command(command, remainder)
        except ValueError as exc:
            await self._send_message(client, int(chat_id), str(exc))
            return

        dependency_status = "bot-only"
        if decision.command == "/ping":
            reply = await handle_ping(self.settings, command_started)
        elif decision.command == "/help":
            reply = await handle_help()
        elif decision.command == "/status":
            reply, services = await handle_status(self.settings, self.openai_client, self.pep_client, self.started_at)
            dependency_status = ",".join(f"{name}={status}" for name, status in services.items())
        elif decision.command == "/brief":
            reply = await handle_brief(decision.prompt, self.settings, self.openai_client, self.memory_store)
            dependency_status = "arbiter-preflight,memory,azure-openai"
        elif decision.command in {"/remember", "/find", "/followup", "/prep", "/draft", "/task"}:
            reply = await handle_operational_command(
                decision.command,
                decision.prompt,
                self.settings,
                self.openai_client,
                self.memory_store,
            )
            dependency_status = "memory,agent-router"
        else:
            reply = "Unknown command. Use /help."

        latency_ms = max(0, round((time.perf_counter() - command_started) * 1000, 2))
        log_event(
            "telegram.command",
            command=decision.command,
            route=decision.command,
            chat_id=chat_id,
            latency_ms=latency_ms,
            dependency_status=dependency_status,
        )
        await self._send_message(client, int(chat_id), reply)

    async def _send_message(self, client: httpx.AsyncClient, chat_id: int, text: str) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        response = await client.post(f"{self.base_url}/sendMessage", json=payload)
        response.raise_for_status()
