from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _split_chat_ids(value: str) -> set[int]:
    ids: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    azure_region: str
    app_version: str
    app_env: str
    bot_poll_interval_seconds: int
    bot_allowed_chat_ids: set[int]
    azure_storage_connection_string: str | None
    azure_storage_container: str
    app_insights_connection_string: str | None
    azure_key_vault_uri: str | None


def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").strip(),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", "").strip(),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip(),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21").strip(),
        azure_region=os.getenv("AZURE_REGION", "eastus").strip(),
        app_version=os.getenv("APP_VERSION", "0.1.0").strip(),
        app_env=os.getenv("APP_ENV", "dev").strip(),
        bot_poll_interval_seconds=max(1, int(os.getenv("BOT_POLL_INTERVAL_SECONDS", "2"))),
        bot_allowed_chat_ids=_split_chat_ids(os.getenv("BOT_ALLOWED_CHAT_IDS", "").strip()),
        azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip() or None,
        azure_storage_container=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts").strip(),
        app_insights_connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip() or None,
        azure_key_vault_uri=os.getenv("AZURE_KEY_VAULT_URI", "").strip() or None,
    )


def validate_settings(settings: Settings) -> None:
    required = {
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "AZURE_OPENAI_ENDPOINT": settings.azure_openai_endpoint,
        "AZURE_OPENAI_API_KEY": settings.azure_openai_api_key,
        "AZURE_OPENAI_DEPLOYMENT": settings.azure_openai_deployment,
        "AZURE_OPENAI_API_VERSION": settings.azure_openai_api_version,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
