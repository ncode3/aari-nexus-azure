"""Private operator surface, separate from PR #1's /api/v1 business platform."""
import hashlib
import hmac
import json
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.arbiter import NexusArbiter
from app.bot import TelegramBotRunner
from app.cohort import handle_cohort
from app.commands import handle_operational_command, handle_ping, handle_help, handle_status
from app.config import get_settings, validate_settings
from app.local_lock import FileLease
from app.model_client import create_model_client
from app.pep_client import PepClient
from app.telemetry import configure_logging


class Command(BaseModel):
    chat_id: int
    text: str = Field(min_length=1, max_length=4096)


def create_app(settings=None, model=None):
    settings = settings or get_settings()
    validate_settings(settings)
    if settings.app_env != 'local' or settings.model_provider != 'ollama':
        raise ValueError('Local API requires the isolated Ollama profile')
    if len(settings.local_api_token) < 32:
        raise ValueError('Set a private NEXUS_LOCAL_API_TOKEN of at least 32 characters')
    if any((settings.azure_key_vault_uri, settings.azure_openai_endpoint, settings.azure_openai_api_key,
            settings.azure_storage_connection_string, settings.azure_storage_account_url,
            settings.app_insights_connection_string, settings.cohort_graph_enabled)):
        raise ValueError('Cloud services must be disabled before starting the local operator')
    if settings.telegram_enabled and os.getenv('NEXUS_TEST_BOT_CONFIRMED') != 'true':
        raise ValueError('Pilot polling requires a separately confirmed test bot; production cutover is not enabled')
    configure_logging(settings)
    model = model or create_model_client(settings)
    started = datetime.now(UTC)
    pep = PepClient(settings)
    runner = TelegramBotRunner(settings, model, pep, started)
    data = Path(settings.nexus_memory_path).resolve().parent
    artifacts = Path(settings.local_artifact_path).resolve()
    # One recovery unit; backups must never silently omit a custom artifact root.
    if artifacts != data / 'artifacts' or Path(settings.nexus_memory_path).name != 'nexus_memory.sqlite3':
        raise ValueError('Local memory and artifacts must share the documented recovery directory')
    documents = artifacts / 'documents'
    documents.mkdir(parents=True, exist_ok=True)
    arbiter = NexusArbiter()

    @asynccontextmanager
    async def lifespan(app):
        with FileLease(data / 'runtime.lock'):
            if settings.telegram_enabled:
                await runner.start()
            try:
                yield
            finally:
                if settings.telegram_enabled:
                    await runner.stop()

    app = FastAPI(title='Nexus local operator', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.memory = runner.memory_store
    app.state.runner = runner

    async def authenticate(request: Request):
        # Block browser rebinding/cross-origin requests as well as invalid credentials.
        if request.headers.get('origin'):
            raise HTTPException(403, 'Browser-origin access is disabled')
        host = request.headers.get('host', '').split(':')[0]
        if host not in {'127.0.0.1', 'localhost', 'testserver'}:
            raise HTTPException(403, 'Local host required')
        supplied = request.headers.get('authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer ' + settings.local_api_token).encode()):
            raise HTTPException(401, 'Unauthorized')

    @app.get('/healthz')
    async def health():
        return {'status': 'ok', 'service': 'nexus-local', 'provider': 'ollama',
                'telegram_polling': settings.telegram_enabled, 'paid_cloud': 'disabled', 'pid': os.getpid()}

    @app.post('/local/command', dependencies=[Depends(authenticate)])
    async def command(body: Command):
        if body.chat_id not in settings.bot_allowed_chat_ids:
            raise HTTPException(403, 'Unauthorized chat')
        name, _, payload = body.text.strip().partition(' ')
        try:
            decision = arbiter.authorize_command(name, payload)
            name, payload = decision.command, decision.prompt
            if name == '/ping':
                answer = await handle_ping(settings, time.perf_counter())
            elif name == '/help':
                answer = await handle_help()
            elif name == '/cohort':
                answer = await handle_cohort(payload, settings)
            elif name == '/status':
                answer, _ = await handle_status(settings, model, pep, started)
            else:
                answer = await handle_operational_command(name, payload, settings, model, runner.memory_store)
            return {'reply': answer}
        except (httpx.HTTPError, TimeoutError):
            raise HTTPException(503, 'Local inference unavailable; no cloud fallback') from None
        except ValueError:
            raise HTTPException(400, 'Invalid command or local model response') from None

    @app.put('/local/documents/{name}', dependencies=[Depends(authenticate)])
    async def store_document(name: str, request: Request):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name):
            raise HTTPException(400, 'Invalid attachment name')
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 1024 * 1024:
                raise HTTPException(413, 'Operator attachments are limited to 1 MiB; use the PR #1 importer for business ingestion')
        document_id = hashlib.sha256(content).hexdigest()
        target = documents / (document_id + '.blob')
        try:
            with target.open('xb') as output:
                output.write(content)
        except FileExistsError:
            pass
        metadata = {'id': document_id, 'name': name, 'bytes': len(content), 'sha256': document_id}
        (documents / (document_id + '.json')).write_text(json.dumps(metadata), encoding='utf-8')
        return metadata

    @app.get('/local/documents', dependencies=[Depends(authenticate)])
    async def find_documents(query: str = ''):
        return [item for path in sorted(documents.glob('*.json'))
                if query.lower() in (item := json.loads(path.read_text(encoding='utf-8')))['name'].lower()][:100]

    @app.get('/local/documents/{document_id}', dependencies=[Depends(authenticate)])
    async def get_document(document_id: str):
        if not re.fullmatch(r'[a-f0-9]{64}', document_id):
            raise HTTPException(404, 'Attachment not found')
        target = documents / (document_id + '.blob')
        if not target.is_file() or target.is_symlink():
            raise HTTPException(404, 'Attachment not found')
        return FileResponse(target, media_type='application/octet-stream', filename=document_id + '.bin')

    return app
