from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AHMED_RAW_BLOB = (
    "raw/20_internal/student-progress/david_mykel_taylor_scholars/2026/"
    "week-01/ahmed-kiel-kamil-progress-report.docx"
)
AHMED_PROCESSED_BLOB = (
    "processed/student-progress/david_mykel_taylor_scholars/2026/"
    "week-01/ahmed-kiel-kamil-progress-report.json"
)


def _url(text: str) -> str | None:
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip() if match else None


def parse_ahmed_report(path: str | Path) -> dict[str, Any]:
    from docx import Document

    source = Path(path).expanduser()
    paragraphs = [p.text.strip() for p in Document(source).paragraphs if p.text.strip()]
    try:
        start = paragraphs.index("Ahmed Kiel-Kamil:") + 1
    except ValueError as exc:
        raise ValueError("Ahmed Kiel-Kamil section was not found") from exc
    end = paragraphs.index("General Mentorship:", start) if "General Mentorship:" in paragraphs[start:] else len(paragraphs)
    section = paragraphs[start:end]
    general_start = paragraphs.index("General Mentorship:", start) + 1 if "General Mentorship:" in paragraphs[start:] else len(paragraphs)
    general = paragraphs[general_start:]

    mode = "learning"
    activities = []
    artifact_count = 0
    for index, text in enumerate(section):
        lowered = text.casefold()
        if lowered in {"learnings", "learnings:", "assignments:"}:
            mode = "assignment" if lowered.startswith("assignment") else "learning"
            continue
        if lowered.startswith("one task:"):
            mode = "practical_competency"
        url = _url(text)
        is_artifact = mode == "assignment" and url is not None
        if is_artifact:
            artifact_count += 1
        activities.append({
            "activity_id": "activity:" + hashlib.sha256(
                f"student:ahmed_h_kiel_kamil|1|{index}|{text}".encode()
            ).hexdigest()[:16],
            "student_id": "student:ahmed_h_kiel_kamil",
            "activity_category": mode,
            "reported_description": text,
            "artifact_type": (
                "student_artifact" if is_artifact
                else "learning_resource" if url
                else None
            ),
            "artifact_url": url,
            "source_blob_path": AHMED_RAW_BLOB,
            "artifact_sha256": None,
            "verification_status": "evidence_submitted" if is_artifact else "reported_only",
            "verified_by": None,
            "verification_date": None,
        })
    for index, text in enumerate(general, start=len(activities)):
        activities.append({
            "activity_id": "activity:" + hashlib.sha256(
                f"student:ahmed_h_kiel_kamil|1|mentor|{index}|{text}".encode()
            ).hexdigest()[:16],
            "student_id": "student:ahmed_h_kiel_kamil",
            "activity_category": "mentor_interaction",
            "reported_description": text,
            "artifact_type": None,
            "artifact_url": None,
            "source_blob_path": AHMED_RAW_BLOB,
            "artifact_sha256": None,
            "verification_status": "reported_only",
            "verified_by": None,
            "verification_date": None,
        })
    source_bytes = source.read_bytes()
    return {
        "schema_version": "1.0",
        "cohort_id": "david_mykel_taylor_scholars",
        "student_id": "student:ahmed_h_kiel_kamil",
        "student_display_name": "Ahmed H. Kiel-Kamil",
        "week_number": 1,
        "source_file_name": source.name,
        "source_blob_path": AHMED_RAW_BLOB,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_size_bytes": len(source_bytes),
        "processed_at": datetime.now(UTC).isoformat(),
        "hours_reported": None,
        "attendance_days": None,
        "submission_timestamp": None,
        "submitted": True,
        "approved": False,
        "evidence_count": artifact_count,
        "missing_fields": ["submission_timestamp", "hours_reported", "attendance_days"],
        "activities": activities,
    }
