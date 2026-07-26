from pathlib import Path

from docx import Document

from app.weekly_report_ingestion import parse_ahmed_report


def test_ahmed_section_is_ingested_without_inventing_hours(tmp_path: Path):
    path = tmp_path / "report.docx"
    document = Document()
    for line in [
        "Another Student:",
        "Assignments:",
        "Other work: https://example.test/other",
        "Ahmed Kiel-Kamil:",
        "Learnings",
        "Linux: https://example.test/course",
        "Assignments:",
        "Data Center Budget: https://example.test/artifact",
        "One Task: I can now make a kubernetes cluster",
        "General Mentorship:",
        "Weekly cybersecurity session",
    ]:
        document.add_paragraph(line)
    document.save(path)
    result = parse_ahmed_report(path)
    assert result["submitted"] is True
    assert result["approved"] is False
    assert result["hours_reported"] is None
    assert result["attendance_days"] is None
    assert result["evidence_count"] == 1
    assert result["activities"][0]["verification_status"] == "reported_only"
    assert result["activities"][1]["verification_status"] == "evidence_submitted"
