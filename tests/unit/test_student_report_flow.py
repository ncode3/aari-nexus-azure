from pathlib import Path
from unittest.mock import patch

from app.student_report_flow import (
    build_week_five_analytics,
    build_week_three_analytics,
    build_week_two_analytics,
    parse_data_center_report,
    parse_individual_progress_log,
    parse_scholar_cohort_report,
)

DOWNLOADS = Path.home() / "Downloads"


def test_cohort_report_extracts_week_two_totals() -> None:
    source = DOWNLOADS / "cohort-progress-report.pdf"
    if not source.exists():
        return
    package = parse_scholar_cohort_report(source)
    assert package["page_count"] == 8
    assert len(package["aggregate_totals"]) == 5
    assert sum(item["total_hours"] for item in package["aggregate_totals"]) == 174
    week_two = [
        item for item in package["weekly_records"] if item["week_ending"] == "2026-07-31"
    ]
    assert len(week_two) == 5
    assert sum(item["hours"] for item in week_two) == 96
    assert sum(item["days"] for item in week_two) == 26


def test_rasheed_validated_copy_has_five_week_two_days() -> None:
    source = DOWNLOADS / "rasheed-jeheeb-progress-log (1).pdf"
    if not source.exists():
        return
    package = parse_individual_progress_log(source)
    assert package["weekly_records"][-1]["days"] == 5


def test_data_center_report_does_not_invent_hours() -> None:
    source = DOWNLOADS / "Progress Report 2.pdf"
    if not source.exists():
        return
    package = parse_data_center_report(source)
    assert len(package["members"]) == 4
    assert package["verified_hours"] is None
    assert all(member["hours"] is None for member in package["members"])
    assert len(package["artifact_urls"]) == 6


def test_parser_accepts_charles_and_missing_attendance_days() -> None:
    text = """Reporting period: July 24 - September 4, 2026
Compiled August 21, 2026
Prepared by Winston Doss
Charles Butler III
3 / 7
18
15
Week ending Friday, August 21, 2026
JC Thomas
Hours 5
Days —
WORK COMPLETED & CONTRIBUTION
Flashed the Raspberry Pi firmware.
SKILL GAINED
Hardware setup.
PROBLEM & RESOLUTION
Resolved a display issue.
EMPLOYER / MENTOR INTERACTION
None this week.
NEXT WEEK'S DELIVERABLE
Complete the robot.
Charles Butler III
Hours 6
Days 5
WORK COMPLETED & CONTRIBUTION
Completed the security orchestration dashboard.
SKILL GAINED
Integrated Cursor.
PROBLEM & RESOLUTION
Managed token limits.
EMPLOYER / MENTOR INTERACTION
Camille Balli and Milton Walker.
NEXT WEEK'S DELIVERABLE
Improve the threat map.
"""
    with (
        patch("app.student_report_flow.pdf_text", return_value=(text, 1)),
        patch("app.student_report_flow.file_sha256", return_value="abc123"),
    ):
        package = parse_scholar_cohort_report(Path("report.pdf"))
    assert package["aggregate_totals"] == [
        {
            "student_name": "Charles Butler III",
            "weeks_filed": 3,
            "weeks_expected": 7,
            "total_hours": 18.0,
            "total_days": 15,
        }
    ]
    records = package["weekly_records"]
    assert [record["student_name"] for record in records] == [
        "JC Thomas",
        "Charles Butler III",
    ]
    assert records[0]["hours"] == 5
    assert records[0]["days"] is None
    assert records[1]["days"] == 5


def test_week_five_analytics_deduplicates_supporting_report() -> None:
    totals = [
        ("Javion Postell", 62, 22, 5),
        ("Rasheed Jeheeb", 67, 22, 5),
        ("Winston Doss", 69.5, 20, 5),
        ("Grayson Roper", 100, 25, 5),
        ("JC Thomas", 80, 16, 5),
        ("Charles Butler III", 18, 15, 3),
    ]
    week = [
        ("Javion Postell", 10, 5),
        ("Rasheed Jeheeb", 14, 5),
        ("Winston Doss", 8, 4),
        ("Grayson Roper", 20, 5),
        ("JC Thomas", 5, None),
        ("Charles Butler III", 6, 5),
    ]
    cohort = {
        "source_sha256": "cohort-sha",
        "aggregate_totals": [
            {
                "student_name": name,
                "weeks_filed": filed,
                "weeks_expected": 7,
                "total_hours": hours,
                "total_days": days,
            }
            for name, hours, days, filed in totals
        ],
        "weekly_records": [
            {
                "student_name": name,
                "week_ending": "2026-08-21",
                "hours": hours,
                "days": days,
                "evidence_urls": [],
            }
            for name, hours, days in week
        ],
    }
    individual = {
        "source_sha256": "individual-sha",
        "weekly_records": [
            {
                "student_name": "Rasheed Jeheeb",
                "week_ending": "2026-08-21",
                "hours": 14,
                "days": 5,
                "evidence_urls": [],
            }
        ],
    }
    output = build_week_five_analytics(cohort, individual)
    assert output["week_5"]["verified_hours"] == 63
    assert output["week_5"]["verified_participant_days"] == 24
    assert output["week_5"]["participant_days_missing_for"] == ["JC Thomas"]
    assert output["cumulative_through_week_5"]["verified_hours"] == 396.5
    assert output["cumulative_through_week_5"]["verified_participant_days"] == 120
    assert output["reporting_completeness"]["submitted_student_weeks"] == 28
    assert output["reporting_completeness"]["completion_percent"] == 93.3
    assert output["supporting_source_check"] == {
        "student": "Rasheed Jeheeb",
        "week_ending": "2026-08-21",
        "matches_authoritative_source": True,
        "counted_in_aggregate": False,
    }


def test_week_two_analytics_separates_verified_and_missing_hours() -> None:
    cohort_source = DOWNLOADS / "cohort-progress-report.pdf"
    data_center_source = DOWNLOADS / "Progress Report 2.pdf"
    if not cohort_source.exists() or not data_center_source.exists():
        return
    output = build_week_two_analytics(
        parse_scholar_cohort_report(cohort_source),
        parse_data_center_report(data_center_source),
    )
    assert output["scholar_cohort"]["week_2"]["verified_hours"] == 96
    assert (
        output["scholar_cohort"]["cumulative_through_week_2"]["verified_hours"] == 174
    )
    assert output["scholar_cohort"]["reporting_completeness"]["completion_percent"] == 100
    assert output["data_center_cohort"]["verified_hours"] is None


def test_week_three_analytics_records_missing_grayson_report() -> None:
    source = DOWNLOADS / "cohort-progress-report (1).pdf"
    if not source.exists():
        return
    output = build_week_three_analytics(parse_scholar_cohort_report(source))
    assert output["week_3"]["verified_hours"] == 60
    assert output["week_3"]["verified_participant_days"] == 16
    assert output["reporting_completeness"]["week_3_submitted_reports"] == 4
    assert output["reporting_completeness"]["week_3_missing_students"] == [
        "Grayson Roper"
    ]
    assert output["cumulative_through_week_3"]["verified_hours"] == 234


def test_week_three_data_center_report_extracts_ahmed_artifacts() -> None:
    source = DOWNLOADS / "Progress Report 3.pdf"
    if not source.exists():
        return
    package = parse_data_center_report(source)
    assert package["page_count"] == 2
    assert package["week_number"] == 3
    assert len(package["members"]) == 4
    ahmed = next(
        member for member in package["members"] if member["reported_name"] == "Ahmed Kiel-Kamil"
    )
    assert len(ahmed["artifact_urls"]) == 10
    assert ahmed["verification_status"] == "evidence_submitted"
    assert package["verified_hours"] is None
