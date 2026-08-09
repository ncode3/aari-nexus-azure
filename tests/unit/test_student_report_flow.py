from pathlib import Path

from app.student_report_flow import (
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
