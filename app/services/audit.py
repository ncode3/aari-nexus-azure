import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AuditEvents

SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "connection_string",
    "document_content",
    "text_content",
}


def _redact(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else item
        for key, item in value.items()
    }


def record_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    request_id: str | None = None,
    source_ip: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    success: bool = True,
    metadata: dict[str, Any] | None = None,
) -> AuditEvents:
    event = AuditEvents(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        source_ip=source_ip,
        before_values=_redact(before),
        after_values=_redact(after),
        success=success,
        metadata_json=_redact(metadata) or {},
    )
    session.add(event)
    session.flush()
    return event

