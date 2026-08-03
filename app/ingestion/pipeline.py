import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.ingestion.adapters.base import IngestionAdapter
from app.ingestion.checksum import sha256_bytes
from app.ingestion.filenames import sanitize_filename
from app.models.entities import (
    DocumentChunks,
    Documents,
    DocumentVersions,
    IngestionEvents,
    WorkflowRuns,
)
from app.repositories.documents import DocumentRepository
from app.services.audit import record_audit
from app.services.object_store import ObjectStore


@dataclass(frozen=True)
class IngestionRequest:
    filename: str
    content_type: str
    content: bytes
    source_system: str
    source_identifier: str
    classification: str = "internal"
    retention_category: str = "program_record"
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestionResult:
    workflow_run_id: uuid.UUID
    document_id: uuid.UUID
    sha256: str
    object_key: str
    status: str
    duplicate: bool
    records_processed: int


class IngestionPipeline:
    def __init__(
        self,
        session: Session,
        object_store: ObjectStore,
        adapters: list[IngestionAdapter],
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.object_store = object_store
        self.settings = settings or get_settings()
        self.adapters = {
            content_type: adapter for adapter in adapters for content_type in adapter.content_types
        }

    def ingest(self, request: IngestionRequest) -> IngestionResult:
        self._validate(request)
        checksum = sha256_bytes(request.content)
        filename = sanitize_filename(request.filename)
        existing = DocumentRepository(self.session).by_checksum(checksum)
        run = WorkflowRuns(
            workflow_type="document_ingestion",
            status="running",
            import_batch_id=str(uuid.uuid4()),
            started_at=datetime.now(UTC),
            records_discovered=1,
            metadata_json={"source_system": request.source_system},
        )
        self.session.add(run)
        self.session.flush()
        if existing:
            self._event(run, existing, request, "deduplicate", "duplicate")
            run.status = "completed"
            run.records_processed = 0
            run.completed_at = datetime.now(UTC)
            record_audit(
                self.session,
                actor=f"ingestion:{request.source_system}",
                action="document.duplicate",
                entity_type="document",
                entity_id=existing.id,
                success=True,
                metadata={"sha256": checksum},
            )
            self.session.commit()
            return IngestionResult(
                run.id,
                existing.id,
                checksum,
                existing.minio_object_key,
                "duplicate",
                True,
                0,
            )

        adapter = self.adapters.get(request.content_type)
        try:
            parsed = adapter.parse(request.content) if adapter else None
            normalized = adapter.normalize(parsed, request.metadata) if adapter else None
        except Exception as exc:
            rejected_key = (
                f"rejected/{datetime.now(UTC):%Y/%m/%d}/{checksum[:12]}-{filename}"
            )
            self.object_store.put(
                self.settings.minio_rejected_bucket,
                rejected_key,
                request.content,
                request.content_type,
            )
            run.status = "failed"
            run.records_rejected = 1
            run.error_summary = f"{type(exc).__name__}: parser rejected source"
            run.completed_at = datetime.now(UTC)
            self.session.add(
                IngestionEvents(
                    workflow_run_id=run.id,
                    document_id=None,
                    event_type="reject",
                    source_system=request.source_system,
                    source_identifier=f"{request.source_identifier}:{run.id}",
                    status="rejected",
                    message=f"{type(exc).__name__}: invalid source format",
                    metadata_json={"filename": filename, "sha256": checksum},
                )
            )
            record_audit(
                self.session,
                actor=f"ingestion:{request.source_system}",
                action="document.reject",
                entity_type="document",
                success=False,
                metadata={"sha256": checksum, "reason": type(exc).__name__},
            )
            self.session.commit()
            raise ValueError(f"Source file was rejected: {type(exc).__name__}") from exc
        object_key = self._object_key(request, filename, checksum)
        self.object_store.put(
            self.settings.minio_documents_bucket,
            object_key,
            request.content,
            request.content_type,
        )
        document = Documents(
            original_filename=filename,
            content_type=request.content_type,
            sha256=checksum,
            file_size=len(request.content),
            minio_bucket=self.settings.minio_documents_bucket,
            minio_object_key=object_key,
            source_system=request.source_system,
            source_url=request.source_url,
            processing_status="processed" if adapter else "stored",
            classification=request.classification,
            retention_category=request.retention_category,
            current_version=1,
            metadata_json={**request.metadata, "source_identifier": request.source_identifier},
        )
        self.session.add(document)
        self.session.flush()
        version = DocumentVersions(
            document_id=document.id,
            version_number=1,
            sha256=checksum,
            file_size=len(request.content),
            minio_object_key=object_key,
            metadata_json={"source_identifier": request.source_identifier},
        )
        self.session.add(version)
        self.session.flush()
        records = self._write_chunks(document, version, normalized)
        self._event(run, document, request, "complete", "processed")
        run.status = "completed"
        run.records_processed = records
        run.completed_at = datetime.now(UTC)
        record_audit(
            self.session,
            actor=f"ingestion:{request.source_system}",
            action="document.create",
            entity_type="document",
            entity_id=document.id,
            success=True,
            metadata={"sha256": checksum, "classification": request.classification},
        )
        self.session.commit()
        return IngestionResult(
            run.id, document.id, checksum, object_key, "processed", False, records
        )

    def _validate(self, request: IngestionRequest) -> None:
        if not request.content:
            raise ValueError("Empty files are not accepted")
        if len(request.content) > self.settings.max_upload_bytes:
            raise ValueError("File exceeds configured upload limit")
        if request.content_type not in self.settings.allowed_mime_types:
            raise ValueError(f"Unsupported MIME type: {request.content_type}")
        if request.classification not in {"public", "internal", "restricted"}:
            raise ValueError("Invalid document classification")

    def _object_key(self, request: IngestionRequest, filename: str, checksum: str) -> str:
        date_prefix = datetime.now(UTC).strftime("%Y/%m/%d")
        return f"{request.classification}/{date_prefix}/{checksum[:12]}-{filename}"

    def _write_chunks(self, document, version, normalized: Any) -> int:
        if not normalized:
            return 1
        pages = normalized.get("pages") if isinstance(normalized, dict) else None
        if pages:
            for sequence, page in enumerate(pages, start=1):
                self.session.add(
                    DocumentChunks(
                        document_id=document.id,
                        document_version_id=version.id,
                        chunk_sequence=sequence,
                        text_content=page["text"],
                        page_number=page["page_number"],
                        metadata_json={},
                    )
                )
            return len(pages)
        # Structured content is kept as metadata lineage, not duplicated into a text chunk.
        document.metadata_json = {
            **document.metadata_json,
            "parsed_record_count": len(normalized) if isinstance(normalized, list) else 1,
            "parsed_preview_schema": (
                sorted(normalized[0]) if isinstance(normalized, list) and normalized else None
            ),
        }
        return len(normalized) if isinstance(normalized, list) else 1

    def _event(self, run, document, request, event_type: str, status: str) -> None:
        self.session.add(
            IngestionEvents(
                workflow_run_id=run.id,
                document_id=document.id,
                event_type=event_type,
                source_system=request.source_system,
                source_identifier=f"{request.source_identifier}:{run.id}",
                status=status,
                message=None,
                metadata_json={"filename": sanitize_filename(request.filename)},
            )
        )
