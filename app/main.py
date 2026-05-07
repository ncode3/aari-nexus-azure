from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.azure_openai_client import AzureOpenAIClient
from app.bot import TelegramBotRunner
from app.config import get_settings, validate_settings
from app.pep_client import PepClient
from app.telemetry import configure_logging, log_event


settings = get_settings()
validate_settings(settings)
configure_logging(settings)
started_at = datetime.now(UTC)
openai_client = AzureOpenAIClient(settings)
pep_client = PepClient(settings)
bot_runner = TelegramBotRunner(settings, openai_client, pep_client, started_at)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_event("app.start", app_version=settings.app_version, region=settings.azure_region)
    await bot_runner.start()
    try:
        yield
    finally:
        await bot_runner.stop()
        log_event("app.stop")


app = FastAPI(title="AARI Nexus Azure", version=settings.app_version, lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "aari-nexus-azure",
        "version": settings.app_version,
        "region": settings.azure_region,
    }
