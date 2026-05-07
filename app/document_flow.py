from __future__ import annotations

from app.intake import StudentIntakeRecord


def summarize_document_flow(record: StudentIntakeRecord) -> dict[str, object]:
    return {
        "student_id": record.student_id,
        "intake_status": record.intake_status,
        "document_types": [doc.document_type for doc in record.documents],
        "document_count": len(record.documents),
    }

