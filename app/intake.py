from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeDocument:
    filename: str
    document_type: str
    storage_path: str


@dataclass(frozen=True)
class StudentIntakeRecord:
    student_id: str
    intake_status: str
    documents: tuple[IntakeDocument, ...]


def classify_document(filename: str) -> str:
    lowered = filename.lower()
    if "resume" in lowered:
        return "resume"
    if "cover" in lowered:
        return "cover-letter"
    if "transcript" in lowered:
        return "transcript"
    return "supporting-document"


def build_student_intake_record(student_id: str, filenames: list[str], base_path: str) -> StudentIntakeRecord:
    documents = tuple(
        IntakeDocument(
            filename=name,
            document_type=classify_document(name),
            storage_path=f"{base_path.rstrip('/')}/{name}",
        )
        for name in filenames
    )
    return StudentIntakeRecord(
        student_id=student_id,
        intake_status="documents-received" if documents else "awaiting-documents",
        documents=documents,
    )

