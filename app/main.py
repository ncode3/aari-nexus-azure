from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes.analytics import router as analytics_router
from app.api.routes.documents import router as documents_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.programs import router as programs_router
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Keep the legacy Telegram operator available only when explicitly enabled."""
    bot_runner = None
    if settings.enable_telegram_bot:
        from app.azure_openai_client import AzureOpenAIClient
        from app.bot import TelegramBotRunner
        from app.config import get_settings as get_legacy_settings
        from app.config import validate_settings
        from app.pep_client import PepClient

        legacy_settings = get_legacy_settings()
        validate_settings(legacy_settings)
        bot_runner = TelegramBotRunner(
            legacy_settings,
            AzureOpenAIClient(legacy_settings),
            PepClient(legacy_settings),
            datetime.now(UTC),
        )
        await bot_runner.start()
    try:
        yield
    finally:
        if bot_runner:
            await bot_runner.stop()


app = FastAPI(
    title="AARI Data Platform",
    version="0.1.0",
    description="Portable system of record for AARI programs and evidence.",
    lifespan=lifespan,
)
app.include_router(documents_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(programs_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {"code": "validation_error", "message": str(exc)},
            "request_id": request.state.request_id,
        },
    )


@app.get("/health")
@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aari-data-platform", "version": "0.1.0"}


@app.get("/ready")
def ready() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
