import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import WorkflowRuns

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/jobs", status_code=202)
def create_job() -> dict:
    return {
        "status": "upload_required",
        "upload_endpoint": "/api/v1/documents",
        "message": "Submit the source file and metadata as multipart form data.",
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    run = db.get(WorkflowRuns, job_id)
    if not run:
        raise HTTPException(404, "Ingestion job not found")
    return {
        "id": run.id,
        "workflow_type": run.workflow_type,
        "status": run.status,
        "records_discovered": run.records_discovered,
        "records_processed": run.records_processed,
        "records_rejected": run.records_rejected,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_summary": run.error_summary,
    }

