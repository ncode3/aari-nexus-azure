import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import pagination
from app.db.session import get_db
from app.ingestion.adapters import CsvAdapter, JsonAdapter, PdfAdapter, XlsxAdapter
from app.ingestion.pipeline import IngestionPipeline, IngestionRequest
from app.models.entities import Documents
from app.repositories.documents import DocumentRepository
from app.services.object_store import MinioObjectStore

router = APIRouter(prefix="/documents", tags=["documents"])


def _document(document: Documents) -> dict:
    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "sha256": document.sha256,
        "file_size": document.file_size,
        "source_system": document.source_system,
        "processing_status": document.processing_status,
        "classification": document.classification,
        "ingested_at": document.ingested_at,
        "metadata": document.metadata_json,
    }


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    source_system: str = Form("api"),
    source_identifier: str | None = Form(None),
    classification: str = Form("internal"),
    db: Session = Depends(get_db),
) -> dict:
    content = await file.read()
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0]
    if not content_type:
        raise HTTPException(415, "Content type is required")
    pipeline = IngestionPipeline(
        db,
        MinioObjectStore(),
        [CsvAdapter(), XlsxAdapter(), JsonAdapter(), PdfAdapter()],
    )
    result = pipeline.ingest(
        IngestionRequest(
            filename=file.filename or "upload",
            content_type=content_type,
            content=content,
            source_system=source_system,
            source_identifier=source_identifier or file.filename or "upload",
            classification=classification,
        )
    )
    return {
        "document_id": result.document_id,
        "ingestion_job_id": result.workflow_run_id,
        "status": result.status,
        "duplicate": result.duplicate,
        "sha256": result.sha256,
    }


@router.get("")
def list_documents(
    page: tuple[int, int] = Depends(pagination), db: Session = Depends(get_db)
) -> dict:
    offset, limit = page
    items = DocumentRepository(db).page(
        offset=offset,
        limit=limit,
        statement=select(Documents).where(Documents.deleted_at.is_(None)),
    )
    total = db.scalar(
        select(func.count()).select_from(Documents).where(Documents.deleted_at.is_(None))
    )
    return {"items": [_document(item) for item in items], "total": total, "offset": offset, "limit": limit}


@router.get("/{document_id}")
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    document = DocumentRepository(db).get_active(document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return _document(document)

