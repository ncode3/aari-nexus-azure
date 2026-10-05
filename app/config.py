from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


KEY_VAULT_SECRET_NAMES = {
    "TELEGRAM_BOT_TOKEN": "telegram-bot-token",
    "AZURE_OPENAI_ENDPOINT": "azure-openai-endpoint",
    "AZURE_OPENAI_API_KEY": "azure-openai-api-key",
    "AZURE_OPENAI_DEPLOYMENT": "azure-openai-deployment",
    "AZURE_OPENAI_API_VERSION": "azure-openai-api-version",
}


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
    azure_storage_account_url: str | None
    azure_storage_container: str
    app_insights_connection_string: str | None
    azure_key_vault_uri: str | None
    pep_base_url: str
    pep_health_timeout_seconds: float
    model_timeout_seconds: float
    nexus_memory_path: str
    nexus_debug_json: bool
    azure_client_id: str | None = None
    cohort_graph_enabled: bool = False
    cohort_site_id: str = ""
    cohort_site_url: str = "https://aari.sharepoint.com/sites/AARICohortDesk"
    cohort_list_id: str = "c2b94b21-d99a-4608-8939-5fed06a86cde"
    cohort_app_url: str = "https://apps.powerapps.com/play/e/default-b13dd871-64d2-4218-abc5-b6f813344921/a/faf9263b-6527-4763-a10d-db68e207e4fa?tenantId=b13dd871-64d2-4218-abc5-b6f813344921"
    cohort_queue_url: str = "https://aari.sharepoint.com/sites/AARICohortDesk/Lists/Cohort%20Registrations/Followup%20Queue.aspx"
    cohort_summary_url: str = "https://aari.sharepoint.com/sites/AARICohortDesk/Lists/Cohort%20Registrations/Cohort%20Summary.aspx"
    cohort_max_pages: int = 100


def _get_secret_client(vault_uri: str) -> SecretClient:
    return SecretClient(vault_url=vault_uri, credential=DefaultAzureCredential())


def _normalize_pep_base_url(value: str) -> str:
    cleaned = value.strip() or "http://localhost:8081"
    parsed = urlparse(cleaned)
    if not parsed.scheme:
        parsed = urlparse(f"http://{cleaned}")
    hostname = parsed.hostname or "localhost"
    if hostname == "0.0.0.0":
        hostname = "localhost"
    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    return urlunparse((parsed.scheme or "http", netloc, parsed.path.rstrip("/"), "", "", ""))


def _get_env_or_key_vault(name: str, vault_uri: str | None) -> str:
    direct_value = os.getenv(name, "").strip()
    if direct_value:
        return direct_value
    if not vault_uri:
        return ""
    secret_name = KEY_VAULT_SECRET_NAMES[name]
    client = _get_secret_client(vault_uri)
    return client.get_secret(secret_name).value.strip()


def get_settings() -> Settings:
    azure_key_vault_uri = os.getenv("AZURE_KEY_VAULT_URI", "").strip() or None
    return Settings(
        telegram_bot_token=_get_env_or_key_vault("TELEGRAM_BOT_TOKEN", azure_key_vault_uri),
        azure_openai_endpoint=_get_env_or_key_vault("AZURE_OPENAI_ENDPOINT", azure_key_vault_uri),
        azure_openai_api_key=_get_env_or_key_vault("AZURE_OPENAI_API_KEY", azure_key_vault_uri),
        azure_openai_deployment=_get_env_or_key_vault("AZURE_OPENAI_DEPLOYMENT", azure_key_vault_uri),
        azure_openai_api_version=_get_env_or_key_vault("AZURE_OPENAI_API_VERSION", azure_key_vault_uri) or "2024-10-21",
        azure_region=os.getenv("AZURE_REGION", "eastus").strip(),
        app_version=os.getenv("APP_VERSION", "0.3.0").strip(),
        app_env=os.getenv("APP_ENV", "dev").strip(),
        bot_poll_interval_seconds=max(1, int(os.getenv("BOT_POLL_INTERVAL_SECONDS", "2"))),
        bot_allowed_chat_ids=_split_chat_ids(os.getenv("BOT_ALLOWED_CHAT_IDS", "").strip()),
        azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip() or None,
        azure_storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL", "").strip() or None,
        azure_storage_container=os.getenv("AZURE_STORAGE_CONTAINER", "artifacts").strip(),
        app_insights_connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip() or None,
        azure_key_vault_uri=azure_key_vault_uri,
        pep_base_url=_normalize_pep_base_url(os.getenv("PEP_BASE_URL", "http://localhost:8081")),
        pep_health_timeout_seconds=max(0.1, float(os.getenv("PEP_HEALTH_TIMEOUT_SECONDS", "1"))),
        model_timeout_seconds=max(1.0, float(os.getenv("MODEL_TIMEOUT_SECONDS", "20"))),
        nexus_memory_path=os.getenv("NEXUS_MEMORY_PATH", str(BASE_DIR / "data" / "nexus_memory.sqlite3")).strip(),
        azure_client_id=os.getenv("AZURE_CLIENT_ID", "").strip() or None,
        cohort_graph_enabled=os.getenv("COHORT_GRAPH_ENABLED", "false").lower() in {"true", "1", "yes"},
        cohort_site_id=os.getenv("COHORT_SITE_ID", "").strip(),
        cohort_site_url=os.getenv("COHORT_SITE_URL", Settings.cohort_site_url).strip(),
        cohort_list_id=os.getenv("COHORT_LIST_ID", Settings.cohort_list_id).strip(),
        cohort_app_url=os.getenv("COHORT_APP_URL", Settings.cohort_app_url).strip(),
        cohort_queue_url=os.getenv("COHORT_QUEUE_URL", Settings.cohort_queue_url).strip(),
        cohort_summary_url=os.getenv("COHORT_SUMMARY_URL", Settings.cohort_summary_url).strip(),
        cohort_max_pages=max(1, int(os.getenv("COHORT_MAX_PAGES", "100"))),
        nexus_debug_json=os.getenv("NEXUS_DEBUG_JSON", "").strip().lower() in {"1", "true", "yes"},
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
