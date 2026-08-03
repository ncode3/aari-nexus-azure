from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import DocumentChunks, Documents

router = APIRouter(tags=["analytics"])


@router.get("/financial/summary")
def financial_summary(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(text("SELECT * FROM financial_summary ORDER BY currency, fund_restriction"))
    return {"items": [dict(row) for row in rows.mappings()]}


@router.get("/search")
def search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    safe = q.replace("%", r"\%").replace("_", r"\_")
    pattern = f"%{safe}%"
    documents = list(
        db.scalars(
            select(Documents)
            .where(Documents.original_filename.ilike(pattern, escape="\\"))
            .limit(limit)
        )
    )
    remaining = max(0, limit - len(documents))
    chunks = list(
        db.scalars(
            select(DocumentChunks)
            .where(DocumentChunks.text_content.ilike(pattern, escape="\\"))
            .limit(remaining)
        )
    )
    return {
        "documents": [
            {"id": item.id, "filename": item.original_filename, "classification": item.classification}
            for item in documents
        ],
        "chunks": [
            {
                "document_id": item.document_id,
                "page_number": item.page_number,
                "section_heading": item.section_heading,
                "excerpt": item.text_content[:500],
            }
            for item in chunks
        ],
    }
