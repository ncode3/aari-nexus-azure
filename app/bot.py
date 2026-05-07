from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from app.arbiter import NexusArbiter
from app.azure_openai_client import AzureOpenAIClient
from app.commands import handle_brief, handle_help, handle_ping, handle_status
from app.config import Settings
from app.telemetry import log_event


class TelegramBotRunner:
    def __init__(self, settings: Settings, openai_client: AzureOpenAIClient, started_at: datetime) -> None:
        self.settings = settings
        self.openai_client = openai_client
        self.started_at = started_at
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._offset = 0
        self._logger = logging.getLogger("aari-nexus-azure.bot")
        self._arbiter = NexusArbiter()

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
        try:
            decision = self._arbiter.authorize_command(command, remainder)
        except ValueError as exc:
            await self._send_message(client, int(chat_id), str(exc))
            return

        if decision.command == "/ping":
            reply = await handle_ping()
        elif decision.command == "/help":
            reply = await handle_help()
        elif decision.command == "/status":
            reply = await handle_status(self.settings, self.openai_client, self.started_at)
        elif decision.command == "/brief":
            reply = await handle_brief(decision.prompt, self.settings, self.openai_client)
        else:
            reply = "Unknown command. Use /help."

        log_event("telegram.command", command=decision.command, chat_id=chat_id)
        await self._send_message(client, int(chat_id), reply)

    async def _send_message(self, client: httpx.AsyncClient, chat_id: int, text: str) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        response = await client.post(f"{self.base_url}/sendMessage", json=payload)
        response.raise_for_status()
