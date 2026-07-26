from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlparse

EVIDENCE_STATUSES = {"reported_only", "evidence_submitted", "mentor_verified", "completed"}
ASSESSMENT_STAGES = ("baseline", "midpoint", "final")
COMPETENCY_CATEGORIES = (
    "Linux",
    "command line",
    "cloud",
    "networking",
    "server hardware",
    "data-center operations",
    "cybersecurity",
    "robotics",
    "ROS",
    "career readiness",
)
PRACTICAL_LEVELS = (
    "not_attempted",
    "attempted",
    "completed_with_help",
    "completed_independently",
    "can_teach_others",
)
PRACTICAL_COMPETENCIES = (
    "SSH",
    "Linux file and permission management",
    "Network configuration",
    "VLANs",
    "Firewall configuration",
    "Server documentation",
    "Jetson configuration",
    "ROS nodes and topics",
    "RViz",
    "URDF",
    "Sensor integration",
    "Cloud resource deployment",
)
CAREER_RECORD_TYPES = (
    "original_resume",
    "current_resume",
    "resume_review",
    "portfolio",
    "linkedin",
    "github_profile",
    "project_demonstration",
    "mock_interview",
    "application",
    "interview",
    "offer",
    "employment_start",
    "starting_salary",
)

WEEK1_SOURCE = (
    "processed/student-progress/david_mykel_taylor_scholars/2026/"
    "week-01/cohort-progress-report.json"
)
BASELINE_SOURCE = (
    "processed/student-progress/summer-2026-data-center/2026/assessments/"
    "baseline/technical-skills-assessment.json"
)
COURSERA_SOURCE = (
    "processed/learning-platforms/coursera/aari-google-learning-program/"
    "2026/learner-roster.json"
)


def _now(value: str | None = None) -> str:
    return value or datetime.now(UTC).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def evidence_metric(
    value: Any,
    evidence_status: str,
    source_blob_path: str,
    last_updated: str,
) -> dict[str, Any]:
    if evidence_status not in EVIDENCE_STATUSES | {"self_reported_recalculated", "pending"}:
        raise ValueError(f"Unsupported evidence status: {evidence_status}")
    return {
        "value": value,
        "evidence_status": evidence_status,
        "source_blob_path": source_blob_path,
        "last_updated": last_updated,
    }


def build_baseline_summary(
    assessment: Mapping[str, Any],
    *,
    source_blob_path: str = BASELINE_SOURCE,
    last_updated: str | None = None,
) -> dict[str, Any]:
    updated = _now(last_updated)
    responses = assessment["responses"]
    response_ids = [item["response_id"] for item in responses]
    linked = [item for item in responses if item.get("participant_id")]
    aggregate = {
        name: evidence_metric(value, "self_reported_recalculated", source_blob_path, updated)
        for name, value in assessment["aggregate"].items()
    }
    return {
        "schema_version": "2.0",
        "assessment_stage": assessment["assessment_stage"],
        "assessment_type": assessment["assessment_type"],
        "assessment_window": assessment["assessment_window"],
        "assessment_date": assessment["assessment_window"]["start"][:10],
        "question_count": 6,
        "response_count": len(responses),
        "all_responses_preserved": len(responses) == assessment["response_count"],
        "question_level_processing": True,
        "person_level_linkage": {
            "mode": assessment["linkage_mode"],
            "linked_responses": len(linked),
            "unlinked_responses": len(responses) - len(linked),
            "duplicate_response_ids": len(response_ids) - len(set(response_ids)),
            "identity_duplicates_detectable": bool(linked),
        },
        "aggregate_metrics": aggregate,
        "source_sha256": assessment["ingestion"]["raw_sha256"],
        "raw_source_blob_path": assessment["ingestion"]["raw_blob_path"],
        "processed_source_blob_path": source_blob_path,
        "last_updated": updated,
    }


def build_reporting_completeness(
    week: Mapping[str, Any],
    *,
    due_date: str = "2026-07-24T15:00:00-04:00",
    last_updated: str | None = None,
) -> dict[str, Any]:
    updated = _now(last_updated)
    expected = [
        ("student:ahmed_h_kiel_kamil", "Ahmed H. Kiel-Kamil"),
        ("student:javion_postell", "Javion Postell"),
        ("student:rasheed_jeheeb", "Rasheed Jeheeb"),
        ("student:winston_doss", "Winston Doss"),
        ("student:grayson_roper", "Grayson Roper"),
        ("student:jc_thomas", "JC Thomas"),
    ]
    submitted = {student["name"]: student for student in week["students"]}
    rows = []
    for student_id, name in expected:
        record = submitted.get(name)
        rows.append({
            "cohort_id": "david_mykel_taylor_scholars",
            "student_id": student_id,
            "student_display_name": name,
            "week_number": 1,
            "due_date": due_date,
            "submitted": record is not None,
            "submission_timestamp": None,
            "approved": bool(record and week["validation"]["passed"]),
            "late": True if record is None else None,
            "hours_reported": record["hours"] if record else None,
            "evidence_count": len(record.get("evidence_links", [])) if record else 0,
            "missing_fields": (
                ["submission_timestamp"]
                if record
                else ["submission", "submission_timestamp", "hours_reported", "evidence"]
            ),
        })
    submitted_count = sum(row["submitted"] for row in rows)
    verified_hours = sum(row["hours_reported"] or 0 for row in rows if row["approved"])
    verified_days = sum(student["attendance_days"] for student in week["students"])
    return {
        "schema_version": "1.0",
        "cohort_id": "david_mykel_taylor_scholars",
        "week_number": 1,
        "source_blob_path": WEEK1_SOURCE,
        "last_updated": updated,
        "expected_submission_table": rows,
        "metrics": {
            "expected_reports": evidence_metric(len(rows), "completed", WEEK1_SOURCE, updated),
            "submitted_reports": evidence_metric(submitted_count, "completed", WEEK1_SOURCE, updated),
            "missing_reports": evidence_metric(len(rows) - submitted_count, "completed", WEEK1_SOURCE, updated),
            "reporting_completion_percent": evidence_metric(
                round(submitted_count / len(rows) * 100, 2), "completed", WEEK1_SOURCE, updated
            ),
            "verified_hours": evidence_metric(verified_hours, "completed", WEEK1_SOURCE, updated),
            "verified_participant_days": evidence_metric(
                verified_days, "completed", WEEK1_SOURCE, updated
            ),
        },
        "outstanding_students": [
            {"student_id": row["student_id"], "student_display_name": row["student_display_name"]}
            for row in rows if not row["submitted"]
        ],
    }


def _artifact_type(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url.replace("\n", "")).netloc.lower()
    if host == "github.com":
        return "github"
    if host.endswith("linkedin.com"):
        return "linkedin"
    if host == "docs.google.com":
        return "google_document"
    return "web_resource"


def build_weekly_activities(
    week: Mapping[str, Any], *, last_updated: str | None = None
) -> list[dict[str, Any]]:
    updated = _now(last_updated)
    activities = []
    for student in week["students"]:
        student_id = f"student:{_slug(student['name'])}"
        descriptions = student.get("work_completed", []) or [""]
        artifacts = student.get("evidence_links", [])
        count = max(len(descriptions), len(artifacts), 1)
        for index in range(count):
            description = descriptions[min(index, len(descriptions) - 1)] if descriptions else ""
            artifact = artifacts[index] if index < len(artifacts) else None
            canonical = f"{student_id}|1|{index}|{description}|{artifact or ''}"
            activities.append({
                "activity_id": "activity:" + hashlib.sha256(canonical.encode()).hexdigest()[:16],
                "student_id": student_id,
                "activity_category": "weekly_technical_and_career_activity",
                "reported_description": description,
                "artifact_type": _artifact_type(artifact),
                "artifact_url": artifact,
                "source_blob_path": WEEK1_SOURCE,
                "artifact_sha256": None,
                "verification_status": "evidence_submitted" if artifact else "reported_only",
                "verified_by": None,
                "verification_date": None,
                "sponsor_id": None,
                "grant_id": None,
                "program_id": "program:david_mykel_taylor_scholars",
                "cohort_id": "david_mykel_taylor_scholars",
                "project_id": None,
                "last_updated": updated,
            })
    return activities


def build_skill_measurements(
    baseline: Mapping[str, Any], *, last_updated: str | None = None
) -> list[dict[str, Any]]:
    updated = _now(last_updated)
    aggregate = baseline["aggregate"]
    mapping = {
        "Linux": aggregate["linux_experience_mean"],
        "command line": aggregate["command_line_experience_mean"],
        "cloud": aggregate["public_cloud_experience_percent"],
        "networking": aggregate["networking_familiarity_percent"],
        "server hardware": aggregate["server_build_experience_percent"],
        "career readiness": aggregate["job_market_ready_percent"],
    }
    records = []
    for competency in COMPETENCY_CATEGORIES:
        baseline_value = mapping.get(competency)
        records.append({
            "competency_category": competency,
            "unit": "mean_1_to_5" if competency in {"Linux", "command line"} else "percent",
            "baseline": {
                "self_assessment_score": baseline_value,
                "objective_assessment_score": None,
                "mentor_assessment_score": None,
                "evidence_status": "self_reported_recalculated" if baseline_value is not None else "pending",
            },
            "midpoint": {
                "self_assessment_score": None,
                "objective_assessment_score": None,
                "mentor_assessment_score": None,
                "evidence_status": "pending",
            },
            "final": {
                "self_assessment_score": None,
                "objective_assessment_score": None,
                "mentor_assessment_score": None,
                "evidence_status": "pending",
            },
            "baseline_to_midpoint_change": None,
            "baseline_to_final_change": None,
            "source_blob_path": BASELINE_SOURCE,
            "last_updated": updated,
        })
    return records


def enhance_coursera(
    coursera: Mapping[str, Any], *, last_updated: str | None = None
) -> dict[str, Any]:
    updated = _now(last_updated)
    output = dict(coursera)
    records = []
    for source in coursera["records"]:
        record = dict(source)
        normalized = record["normalized_name"].casefold()
        record["person_id"] = (
            "student:javion_postell" if normalized == "javion postell"
            else "student:ahmed_h_kiel_kamil" if normalized.startswith("ahmed h kiel")
            else None
        )
        record.update({
            "course_name": None,
            "enrollment_date": record.get("join_date"),
            "progress_percentage": None,
            "learning_hours": None,
            "completion_date": None,
            "certificate": None,
            "certificate_verification": None,
            "last_updated": updated,
        })
        records.append(record)
    output["records"] = records
    output["schema_version"] = "2.0"
    output["last_updated"] = updated
    return output


def build_practical_competencies(
    week: Mapping[str, Any], *, last_updated: str | None = None
) -> list[dict[str, Any]]:
    updated = _now(last_updated)
    patterns = {
        "SSH": r"\bssh\b",
        "Linux file and permission management": r"\blinux\b",
        "Network configuration": r"network configuration",
        "Firewall configuration": r"\bfirewall\b",
        "Server documentation": r"server details|server documentation|document server",
        "Jetson configuration": r"jetson",
        "ROS nodes and topics": r"\bros\b",
    }
    records = []
    for student in week["students"]:
        description = " ".join(student.get("work_completed", []))
        for competency, pattern in patterns.items():
            if re.search(pattern, description, re.IGNORECASE):
                records.append({
                    "student_id": f"student:{_slug(student['name'])}",
                    "competency": competency,
                    "level": "attempted",
                    "verification_status": "reported_only",
                    "source_blob_path": WEEK1_SOURCE,
                    "artifact_sha256": None,
                    "verified_by": None,
                    "verification_date": None,
                    "last_updated": updated,
                })
    return records


def build_career_readiness_records(
    week: Mapping[str, Any], *, last_updated: str | None = None
) -> list[dict[str, Any]]:
    updated = _now(last_updated)
    records = []
    checklist_map = {
        "technical_portfolio": "portfolio",
        "updated_resume": "current_resume",
        "linkedin_profile_updated": "linkedin",
        "short_project_demonstration": "project_demonstration",
        "internship_or_employment_next_step": "application",
    }
    for name, checklist in week["checklist_status"].items():
        for field, record_type in checklist_map.items():
            if checklist.get(field):
                records.append({
                    "student_id": f"student:{_slug(name)}",
                    "record_type": record_type,
                    "version": "week-01",
                    "status": "reported_complete",
                    "verification_status": "reported_only",
                    "source_blob_path": WEEK1_SOURCE,
                    "last_updated": updated,
                })
    for student in week["students"]:
        description = " ".join(student.get("work_completed", []))
        if re.search(r"mock interview", description, re.IGNORECASE):
            records.append({
                "student_id": f"student:{_slug(student['name'])}",
                "record_type": "mock_interview",
                "version": "week-01",
                "status": "reported_complete",
                "verification_status": "reported_only",
                "source_blob_path": WEEK1_SOURCE,
                "last_updated": updated,
            })
    return records


def build_student_outcomes(
    week: Mapping[str, Any],
    baseline: Mapping[str, Any],
    coursera: Mapping[str, Any],
    *,
    last_updated: str | None = None,
) -> dict[str, Any]:
    updated = _now(last_updated)
    reporting = build_reporting_completeness(week, last_updated=updated)
    activities = build_weekly_activities(week, last_updated=updated)
    enhanced_coursera = enhance_coursera(coursera, last_updated=updated)
    supported_activities = sum(a["verification_status"] != "reported_only" for a in activities)
    technical_artifacts = sum(a["artifact_type"] in {"github", "google_document"} for a in activities)
    return {
        "schema_version": "2.0",
        "last_updated": updated,
        "privacy": {"classification": "internal", "public_access": False, "contains_student_data": True},
        "reporting_completeness": reporting,
        "weekly_activities": activities,
        "skill_measurements": build_skill_measurements(baseline, last_updated=updated),
        "practical_competencies": build_practical_competencies(week, last_updated=updated),
        "practical_competency_schema": {
            "supported_competencies": list(PRACTICAL_COMPETENCIES),
            "levels": list(PRACTICAL_LEVELS),
        },
        "career_readiness": build_career_readiness_records(week, last_updated=updated),
        "career_record_schema": list(CAREER_RECORD_TYPES),
        "coursera": enhanced_coursera,
        "github_evidence": {
            "identity_mappings": [
                {
                    "student_id": activity["student_id"],
                    "github_url": activity["artifact_url"],
                    "mapping_status": "candidate",
                    "verification_status": "evidence_submitted",
                }
                for activity in activities if activity["artifact_type"] == "github"
            ],
            "contribution_types": [
                "assigned_issue", "pull_request", "accepted_contribution",
                "code_review", "documentation_artifact", "demonstration",
            ],
            "verified_contributions": [],
        },
        "sponsor_attribution": {
            "resources": [
                {
                    "sponsor": "QTS",
                    "grant": "2026 general operating grant",
                    "funding_amount_usd": 15000,
                    "in_kind_resource": None,
                    "program": None,
                    "cohort": None,
                    "project": None,
                    "outcomes_attributed": [],
                    "evidence_status": "completed",
                    "source_blob_path": (
                        "raw/20_internal/02_grants_funding/2026/"
                        "2026-06-17 - QTS Grant Award Notification for AARI.md"
                    ),
                    "last_updated": updated,
                },
                {
                    "sponsor": "a16z Cultural Leadership Fund",
                    "grant": "Ecosystem Partner Program",
                    "funding_amount_usd": 43127.94,
                    "in_kind_resource": "strategic collaboration",
                    "program": None,
                    "cohort": None,
                    "project": None,
                    "outcomes_attributed": [],
                    "evidence_status": "completed",
                    "source_blob_path": (
                        "raw/20_internal/02_grants_funding/2026/"
                        "2026-06 - a16z CLF Ecosystem Partner Acceptance.md"
                    ),
                    "last_updated": updated,
                },
            ],
            "aggregate_reporting_policy": "aggregate_only_without_individual_consent",
        },
        "aggregate_metrics": {
            "verified_hours": reporting["metrics"]["verified_hours"],
            "verified_participant_days": reporting["metrics"]["verified_participant_days"],
            "reporting_completion_percent": reporting["metrics"]["reporting_completion_percent"],
            "evidence_supported_activities": evidence_metric(
                supported_activities, "completed", WEEK1_SOURCE, updated
            ),
            "technical_artifacts": evidence_metric(
                technical_artifacts, "evidence_submitted", WEEK1_SOURCE, updated
            ),
            "coursera_dashboard_learners": evidence_metric(
                enhanced_coursera["metrics"]["dashboard_total_learners"],
                "evidence_submitted",
                COURSERA_SOURCE,
                updated,
            ),
            "baseline_assessment_responses": evidence_metric(
                baseline["response_count"], "self_reported_recalculated", BASELINE_SOURCE, updated
            ),
        },
        "missing_evidence": [
            "Ahmed H. Kiel-Kamil Week 1 report",
            "Per-student Week 1 submission timestamps",
            "Midpoint technical-skills assessment",
            "Final technical-skills assessment",
            "Objective and mentor competency assessments",
            "Coursera page 2 or authoritative full export",
            "Coursera course, progress, learning-hour, completion, and certificate data",
            "Verified GitHub issues, pull requests, reviews, and accepted contributions",
            "Verified internship, employment, offer, and salary records",
        ],
    }
