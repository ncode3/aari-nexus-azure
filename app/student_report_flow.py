from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

SCHOLAR_NAMES = (
    "Javion Postell",
    "Rasheed Jeheeb",
    "Winston Doss",
    "Grayson Roper",
    "JC Thomas",
    "Charles Butler III",
)
SECTION_NAMES = (
    "WORK COMPLETED & CONTRIBUTION",
    "EVIDENCE",
    "SKILL GAINED",
    "PROBLEM & RESOLUTION",
    "EMPLOYER / MENTOR INTERACTION",
    "NEXT WEEK'S DELIVERABLE",
)


@dataclass(frozen=True)
class ReportRoute:
    raw_blob_path: str
    processed_blob_path: str | None
    cohort: str
    week_number: int
    document_type: str
    status: str = "current"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(BytesIO(path.read_bytes()))
    return "\n".join(page.extract_text() or "" for page in reader.pages), len(reader.pages)


def _urls(text: str) -> list[str]:
    values: list[str] = []
    for match in re.findall(r"https?://[^\s•]+", text):
        value = match.rstrip(".,);]")
        if value not in values:
            values.append(value)
    return values


def _section(text: str, name: str) -> str | None:
    try:
        start = text.index(name) + len(name)
    except ValueError:
        return None
    ends = [text.find(other, start) for other in SECTION_NAMES if other != name]
    valid = [position for position in ends if position >= 0]
    end = min(valid) if valid else len(text)
    value = " ".join(text[start:end].split())
    return value or None


def parse_scholar_cohort_report(path: Path) -> dict[str, Any]:
    text, pages = pdf_text(path)
    compiled = re.search(r"Compiled ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    prepared = re.search(r"Prepared by ([^\n]+)", text)
    reporting_period = re.search(r"Reporting period: ([^·\n]+)", text)
    totals: list[dict[str, Any]] = []
    first_week = text.find("Week ending Friday")
    summary = text[:first_week] if first_week >= 0 else text
    for name in SCHOLAR_NAMES:
        match = re.search(
            rf"{re.escape(name)}\s*\n(\d+)\s*/\s*(\d+)\s*\n([\d.]+)\s*\n(\d+)",
            summary,
        )
        if match:
            totals.append(
                {
                    "student_name": name,
                    "weeks_filed": int(match.group(1)),
                    "weeks_expected": int(match.group(2)),
                    "total_hours": float(match.group(3)),
                    "total_days": int(match.group(4)),
                }
            )

    weekly_records: list[dict[str, Any]] = []
    week_chunks = re.split(r"(?=Week ending Friday, [A-Z][a-z]+ \d{1,2}, \d{4})", text)
    record_pattern = re.compile(
        rf"(?m)^({'|'.join(re.escape(name) for name in SCHOLAR_NAMES)})\s*$"
        r"\s*Hours\s+([\d.]+)\s*\nDays\s+(\d+|[—–-])"
    )
    for chunk in week_chunks:
        ending = re.search(r"Week ending Friday, ([A-Z][a-z]+ \d{1,2}, \d{4})", chunk)
        if not ending:
            continue
        matches = list(record_pattern.finditer(chunk))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(chunk)
            body = chunk[match.end() : end]
            weekly_records.append(
                {
                    "student_name": match.group(1),
                    "week_ending": datetime.strptime(
                        ending.group(1), "%B %d, %Y"
                    ).date().isoformat(),
                    "hours": float(match.group(2)),
                    "days": (
                        None
                        if re.fullmatch(r"[—–-]", match.group(3))
                        else int(match.group(3))
                    ),
                    "work_completed": _section(body, "WORK COMPLETED & CONTRIBUTION"),
                    "skills_gained": _section(body, "SKILL GAINED"),
                    "problem_and_resolution": _section(body, "PROBLEM & RESOLUTION"),
                    "employer_or_mentor_interaction": _section(
                        body, "EMPLOYER / MENTOR INTERACTION"
                    ),
                    "next_week_deliverable": _section(body, "NEXT WEEK'S DELIVERABLE"),
                    "evidence_urls": _urls(body),
                }
            )
    return {
        "schema_version": "1.0",
        "document_type": "cohort_progress_report",
        "cohort": "david_mykel_taylor_scholars",
        "source_filename": path.name,
        "source_sha256": file_sha256(path),
        "page_count": pages,
        "reporting_period": reporting_period.group(1).strip() if reporting_period else None,
        "compiled_date": (
            datetime.strptime(compiled.group(1), "%B %d, %Y").date().isoformat()
            if compiled
            else None
        ),
        "prepared_by": prepared.group(1).strip() if prepared else None,
        "aggregate_totals": totals,
        "weekly_records": weekly_records,
        "evidence_urls": _urls(text),
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def parse_individual_progress_log(path: Path) -> dict[str, Any]:
    text, pages = pdf_text(path)
    student = next((name for name in SCHOLAR_NAMES if name in text), None)
    records = []
    chunks = re.split(r"(?=Week ending Friday, [A-Z][a-z]+ \d{1,2}, \d{4})", text)
    for chunk in chunks:
        ending = re.search(r"Week ending Friday, ([A-Z][a-z]+ \d{1,2}, \d{4})", chunk)
        hours_days = re.search(r"Hours:\s*([\d.]+)\s+Days:\s*(\d+)", chunk)
        if not ending or not hours_days:
            continue
        records.append(
            {
                "student_name": student,
                "week_ending": datetime.strptime(
                    ending.group(1), "%B %d, %Y"
                ).date().isoformat(),
                "hours": float(hours_days.group(1)),
                "days": int(hours_days.group(2)),
                "work_completed": _section(chunk, "WORK COMPLETED & CONTRIBUTION"),
                "skills_gained": _section(chunk, "SKILL GAINED"),
                "problem_and_resolution": _section(chunk, "PROBLEM & RESOLUTION"),
                "employer_or_mentor_interaction": _section(
                    chunk, "EMPLOYER / MENTOR INTERACTION"
                ),
                "next_week_deliverable": _section(chunk, "NEXT WEEK'S DELIVERABLE"),
                "evidence_urls": _urls(chunk),
            }
        )
    return {
        "schema_version": "1.0",
        "document_type": "individual_progress_log",
        "cohort": "david_mykel_taylor_scholars",
        "source_filename": path.name,
        "source_sha256": file_sha256(path),
        "page_count": pages,
        "student_name": student,
        "weekly_records": records,
        "evidence_urls": _urls(text),
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def parse_data_center_report(path: Path) -> dict[str, Any]:
    text, pages = pdf_text(path)
    member_names = (
        "Charles Ryans",
        "Grayson Roper",
        "Charles Butler",
        "Ahmed Kiel-Kamil",
        "Grayson",
        "Butler",
        "Ryans",
        "Ahmed",
    )
    name_patterns = [re.escape(name).replace(r"\ ", r"\s+") for name in member_names]
    member_pattern = re.compile(
        rf"\b({'|'.join(name_patterns)})\s*[-:]\s*", re.IGNORECASE
    )
    matches = list(member_pattern.finditer(text))
    members = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        members.append(
            {
                "reported_name": " ".join(match.group(1).split()),
                "reported_description": " ".join(body.split()),
                "artifact_urls": _urls(body),
                "hours": None,
                "days": None,
                "verification_status": (
                    "evidence_submitted" if _urls(body) else "reported_only"
                ),
            }
        )
    return {
        "schema_version": "1.0",
        "document_type": "data_center_progress_report",
        "cohort": "summer_2026_data_center",
        "source_filename": path.name,
        "source_sha256": file_sha256(path),
        "page_count": pages,
        "week_number": 3 if re.search(r"(?:Report|Week)\s*3", text, re.I) else 2,
        "members": members,
        "artifact_urls": _urls(text),
        "verified_hours": None,
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def serialize_report(package: dict[str, Any]) -> bytes:
    return json.dumps(package, indent=2, sort_keys=True).encode("utf-8")


def build_week_two_analytics(
    cohort_report: dict[str, Any], data_center_report: dict[str, Any]
) -> dict[str, Any]:
    week_two = [
        record
        for record in cohort_report["weekly_records"]
        if record["week_ending"] == "2026-07-31"
    ]
    totals = cohort_report["aggregate_totals"]
    expected_student_weeks = len(totals) * 2
    submitted_student_weeks = sum(item["weeks_filed"] for item in totals)
    evidence_counts = {
        name: sum(
            len(record["evidence_urls"])
            for record in cohort_report["weekly_records"]
            if record["student_name"] == name
        )
        for name in SCHOLAR_NAMES
    }
    return {
        "schema_version": "1.0",
        "last_updated": datetime.now(UTC).isoformat(),
        "privacy": {
            "classification": "internal",
            "contains_student_data": True,
            "public_reporting": "aggregate_only",
        },
        "source_records": [
            {
                "blob_path": (
                    "processed/student-progress/david_mykel_taylor_scholars/2026/"
                    "week-02/cohort-progress-report.json"
                ),
                "sha256": cohort_report["source_sha256"],
                "evidence_status": "completed",
            },
            {
                "blob_path": (
                    "processed/student-progress/summer-2026-data-center/2026/"
                    "week-02/progress-report-2.json"
                ),
                "sha256": data_center_report["source_sha256"],
                "evidence_status": "mentor_reported",
            },
        ],
        "scholar_cohort": {
            "reporting_completeness": {
                "expected_student_weeks": expected_student_weeks,
                "submitted_student_weeks": submitted_student_weeks,
                "completion_percent": round(
                    submitted_student_weeks / expected_student_weeks * 100, 1
                ),
                "missing_students": [],
                "evidence_status": "completed",
            },
            "week_2": {
                "verified_hours": sum(record["hours"] for record in week_two),
                "verified_participant_days": sum(record["days"] for record in week_two),
                "students_reporting": len(week_two),
                "evidence_links": sum(len(record["evidence_urls"]) for record in week_two),
            },
            "cumulative_through_week_2": {
                "verified_hours": sum(item["total_hours"] for item in totals),
                "verified_participant_days": sum(item["total_days"] for item in totals),
                "student_weeks": submitted_student_weeks,
                "evidence_links": sum(evidence_counts.values()),
            },
            "student_totals": [
                {
                    **item,
                    "evidence_links": evidence_counts[item["student_name"]],
                    "evidence_status": "completed",
                }
                for item in totals
            ],
        },
        "data_center_cohort": {
            "members_documented": len(data_center_report["members"]),
            "members_with_submitted_artifact_links": sum(
                member["verification_status"] == "evidence_submitted"
                for member in data_center_report["members"]
            ),
            "submitted_artifact_links": len(data_center_report["artifact_urls"]),
            "verified_hours": None,
            "hours_evidence_status": "missing",
            "artifact_categories": {
                "sql_schema_designs": 3,
                "ui_or_ux_designs": 1,
                "github_applications": 1,
                "training_or_learning_records": 1,
                "firewall_work": {
                    "status": "mentor_reported",
                    "configuration_artifact": False,
                },
            },
        },
        "quality_flags": [
            {
                "type": "superseded_source",
                "student": "Rasheed Jeheeb",
                "detail": (
                    "A four-day Week 2 copy conflicts with the cohort total. "
                    "The five-day source is current and the four-day source is excluded."
                ),
            },
            {
                "type": "hours_missing",
                "cohort": "summer_2026_data_center",
                "detail": "Progress Report 2 documents work and artifacts but provides no hours.",
            },
            {
                "type": "artifact_verification_pending",
                "cohort": "summer_2026_data_center",
                "detail": (
                    "Submitted links are evidence candidates; repository ownership and "
                    "acceptance have not all been independently verified."
                ),
            },
        ],
    }


def build_week_three_analytics(cohort_report: dict[str, Any]) -> dict[str, Any]:
    week_ending = "2026-08-07"
    latest = [
        record
        for record in cohort_report["weekly_records"]
        if record["week_ending"] == week_ending
    ]
    totals = cohort_report["aggregate_totals"]
    expected_student_weeks = len(totals) * 3
    submitted_student_weeks = sum(item["weeks_filed"] for item in totals)
    submitted_names = {record["student_name"] for record in latest}
    expected_names = [item["student_name"] for item in totals]
    missing = [name for name in expected_names if name not in submitted_names]
    return {
        "schema_version": "1.0",
        "last_updated": datetime.now(UTC).isoformat(),
        "privacy": {
            "classification": "internal",
            "contains_student_data": True,
            "public_reporting": "aggregate_only",
        },
        "source_records": [
            {
                "blob_path": (
                    "processed/student-progress/david_mykel_taylor_scholars/2026/"
                    "week-03/cohort-progress-report.json"
                ),
                "sha256": cohort_report["source_sha256"],
                "evidence_status": "completed",
            }
        ],
        "reporting_completeness": {
            "expected_student_weeks": expected_student_weeks,
            "submitted_student_weeks": submitted_student_weeks,
            "completion_percent": round(
                submitted_student_weeks / expected_student_weeks * 100, 1
            ),
            "week_3_expected_reports": len(totals),
            "week_3_submitted_reports": len(latest),
            "week_3_missing_students": missing,
            "evidence_status": "completed",
        },
        "week_3": {
            "verified_hours": sum(record["hours"] for record in latest),
            "verified_participant_days": sum(record["days"] for record in latest),
            "students_reporting": len(latest),
            "evidence_links": sum(len(record["evidence_urls"]) for record in latest),
            "student_records": [
                {
                    "student_name": record["student_name"],
                    "hours": record["hours"],
                    "days": record["days"],
                    "evidence_links": len(record["evidence_urls"]),
                    "evidence_status": "completed",
                }
                for record in latest
            ],
        },
        "cumulative_through_week_3": {
            "verified_hours": sum(item["total_hours"] for item in totals),
            "verified_participant_days": sum(item["total_days"] for item in totals),
            "student_totals": totals,
        },
        "quality_flags": [
            {
                "type": "missing_weekly_report",
                "student": name,
                "week_ending": week_ending,
            }
            for name in missing
        ],
    }


def build_week_five_analytics(
    cohort_report: dict[str, Any], individual_report: dict[str, Any]
) -> dict[str, Any]:
    week_number = 5
    week_ending = "2026-08-21"
    latest = [
        record
        for record in cohort_report["weekly_records"]
        if record["week_ending"] == week_ending
    ]
    totals = cohort_report["aggregate_totals"]
    expected_names = [item["student_name"] for item in totals]
    submitted_names = {record["student_name"] for record in latest}
    missing = [name for name in expected_names if name not in submitted_names]
    missing_days = [
        record["student_name"] for record in latest if record["days"] is None
    ]
    expected_student_weeks = len(totals) * week_number
    submitted_student_weeks = sum(item["weeks_filed"] for item in totals)
    historical_gaps = [
        {
            "student_name": item["student_name"],
            "missing_student_weeks": week_number - item["weeks_filed"],
        }
        for item in totals
        if item["weeks_filed"] < week_number
    ]

    supporting = next(
        (
            record
            for record in individual_report["weekly_records"]
            if record["week_ending"] == week_ending
        ),
        None,
    )
    cohort_rasheed = next(
        (record for record in latest if record["student_name"] == "Rasheed Jeheeb"),
        None,
    )
    supporting_matches = bool(
        supporting
        and cohort_rasheed
        and supporting["hours"] == cohort_rasheed["hours"]
        and supporting["days"] == cohort_rasheed["days"]
    )

    quality_flags: list[dict[str, Any]] = [
        {
            "type": "missing_weekly_report",
            "student": name,
            "week_ending": week_ending,
        }
        for name in missing
    ]
    quality_flags.extend(
        {
            "type": "attendance_days_missing",
            "student": name,
            "week_ending": week_ending,
            "detail": "Hours are reported, but attendance days are not provided.",
        }
        for name in missing_days
    )
    quality_flags.extend(
        {
            "type": "historical_student_week_gap",
            **gap,
            "detail": "The cumulative source reports fewer filed weeks than the current cohort week.",
        }
        for gap in historical_gaps
    )
    if not supporting_matches:
        quality_flags.append(
            {
                "type": "supporting_source_mismatch",
                "student": "Rasheed Jeheeb",
                "week_ending": week_ending,
                "detail": "The individual report does not match the authoritative cohort record.",
            }
        )

    return {
        "schema_version": "1.0",
        "last_updated": datetime.now(UTC).isoformat(),
        "privacy": {
            "classification": "internal",
            "contains_student_data": True,
            "public_reporting": "aggregate_only",
        },
        "source_records": [
            {
                "blob_path": (
                    "processed/student-progress/david_mykel_taylor_scholars/2026/"
                    "week-05/cohort-progress-report.json"
                ),
                "sha256": cohort_report["source_sha256"],
                "role": "authoritative_aggregate",
                "counted_in_aggregate": True,
                "evidence_status": "completed",
            },
            {
                "blob_path": (
                    "processed/student-progress/david_mykel_taylor_scholars/2026/"
                    "week-05/individual/rasheed-jeheeb-progress-log.json"
                ),
                "sha256": individual_report["source_sha256"],
                "role": "supporting_source",
                "counted_in_aggregate": False,
                "evidence_status": (
                    "corroborates_authoritative_source"
                    if supporting_matches
                    else "conflict_requires_review"
                ),
            },
        ],
        "reporting_completeness": {
            "expected_student_weeks": expected_student_weeks,
            "submitted_student_weeks": submitted_student_weeks,
            "completion_percent": round(
                submitted_student_weeks / expected_student_weeks * 100, 1
            ),
            "week_5_expected_reports": len(expected_names),
            "week_5_submitted_reports": len(latest),
            "week_5_missing_students": missing,
            "historical_student_week_gaps": historical_gaps,
            "evidence_status": "completed",
        },
        "week_5": {
            "verified_hours": sum(record["hours"] for record in latest),
            "verified_participant_days": sum(
                record["days"] for record in latest if record["days"] is not None
            ),
            "participant_days_missing_for": missing_days,
            "students_reporting": len(latest),
            "evidence_links": sum(len(record["evidence_urls"]) for record in latest),
            "student_records": [
                {
                    "student_name": record["student_name"],
                    "hours": record["hours"],
                    "days": record["days"],
                    "evidence_links": len(record["evidence_urls"]),
                    "hours_evidence_status": "completed",
                    "days_evidence_status": (
                        "missing" if record["days"] is None else "completed"
                    ),
                }
                for record in latest
            ],
        },
        "cumulative_through_week_5": {
            "verified_hours": sum(item["total_hours"] for item in totals),
            "verified_participant_days": sum(item["total_days"] for item in totals),
            "student_totals": totals,
        },
        "supporting_source_check": {
            "student": "Rasheed Jeheeb",
            "week_ending": week_ending,
            "matches_authoritative_source": supporting_matches,
            "counted_in_aggregate": False,
        },
        "quality_flags": quality_flags,
    }
