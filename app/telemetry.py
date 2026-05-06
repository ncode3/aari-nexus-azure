from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from io import BytesIO

from azure.monitor.opentelemetry import configure_azure_monitor
from azure.storage.blob import BlobServiceClient

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if settings.app_insights_connection_string:
        configure_azure_monitor(connection_string=settings.app_insights_connection_string)


def log_event(event: str, **fields: object) -> None:
    payload = {
        "time": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    logging.getLogger("aari-nexus-azure").info(json.dumps(payload, default=str))


async def upload_artifact(
    settings: Settings,
    artifact_kind: str,
    filename: str,
    payload: dict[str, object],
) -> str | None:
    if not settings.azure_storage_connection_string:
        return None

    service = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
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
    data = json.dumps(payload, indent=2).encode("utf-8")
    container.upload_blob(name=blob_name, data=BytesIO(data), overwrite=True)
    return blob_name
