from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
import uuid

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from app.arbiter import NexusArbiter
from app.config import Settings


ARBITER = NexusArbiter()


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Exporter transport INFO logs must not feed back into the log exporter.
    logging.getLogger("azure").setLevel(logging.WARNING)
    if settings.app_insights_connection_string:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.app_insights_connection_string)


def log_event(event: str, **fields: object) -> None:
    payload = {
        "time": datetime.now(UTC).isoformat(),
        "event": event,
        **ARBITER.redact_fields(fields),
    }
    logging.getLogger("aari-nexus-azure").info(json.dumps(payload, default=str))


async def upload_artifact(
    settings: Settings,
    artifact_kind: str,
    filename: str,
    payload: dict[str, object],
) -> str | None:
    if settings.local_artifact_path:
        # Never accept traversal through artifact names; use a private local root.
        if any(not value or Path(value).name != value or value in {".", ".."}
               or "/" in value or "\\" in value
               for value in (artifact_kind, filename)):
            raise ValueError("Artifact kind and filename must be simple names")
        directory = Path(settings.local_artifact_path) / artifact_kind
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / f"{uuid.uuid4().hex}-{filename}"
        with target.open("x", encoding="utf-8") as output:
            target.chmod(0o600)
            json.dump(ARBITER.redact_fields(payload), output, indent=2)
        return str(target)
    if not settings.azure_storage_connection_string and not settings.azure_storage_account_url:
        return None

    if settings.azure_storage_connection_string:
        service = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    else:
        service = BlobServiceClient(account_url=settings.azure_storage_account_url, credential=DefaultAzureCredential())

    container = service.get_container_client(settings.azure_storage_container)
    try:
        container.create_container()
    except Exception:
        pass

    now = datetime.now(UTC)
    blob_name = (
        f"{artifact_kind}/{settings.app_env}/"
        f"{now.strftime('%Y/%m/%d')}/{now.strftime('%Y%m%dT%H%M%SZ')}-{filename}"
    )
    data = json.dumps(ARBITER.redact_fields(payload), indent=2).encode("utf-8")
    container.upload_blob(name=blob_name, data=BytesIO(data), overwrite=True)
    return blob_name
