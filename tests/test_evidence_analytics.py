from app.evidence_analytics import (
    build_baseline_summary,
    build_reporting_completeness,
    build_skill_measurements,
    build_student_outcomes,
    build_weekly_activities,
    enhance_coursera,
)


UPDATED = "2026-07-26T12:00:00+00:00"


def baseline():
    return {
        "assessment_stage": "baseline",
        "assessment_type": "technical-skills-self-assessment",
        "assessment_window": {
            "start": "2026-01-03T12:00:00+00:00",
            "end": "2026-01-05T12:00:00+00:00",
        },
        "linkage_mode": "cohort-only",
        "response_count": 2,
        "responses": [
            {"response_id": "one", "participant_id": None},
            {"response_id": "two", "participant_id": None},
        ],
        "aggregate": {
            "linux_experience_mean": 1.5,
            "command_line_experience_mean": 2.0,
            "public_cloud_experience_percent": 50.0,
            "server_build_experience_percent": 0.0,
            "networking_familiarity_percent": 50.0,
            "job_market_ready_percent": 0.0,
            "self_reported_readiness_score_mean": 25.0,
        },
        "ingestion": {
            "raw_sha256": "abc",
            "raw_blob_path": "raw/baseline.xlsx",
        },
    }


def week():
    return {
        "validation": {"passed": True},
        "students": [
            {
                "name": "Javion Postell",
                "hours": 12,
                "attendance_days": 3,
                "work_completed": ["Set up Linux."],
                "evidence_links": ["https://example.test/artifact"],
            },
            {
                "name": "Rasheed Jeheeb",
                "hours": 8.5,
                "attendance_days": 3,
                "work_completed": ["Completed a mock interview."],
                "evidence_links": [],
            },
            {
                "name": "Winston Doss",
                "hours": 12.5,
                "attendance_days": 4,
                "work_completed": ["Coordinated the cohort."],
                "evidence_links": [],
            },
            {
                "name": "Grayson Roper",
                "hours": 20,
                "attendance_days": 5,
                "work_completed": ["Practiced network configuration on a Jetson."],
                "evidence_links": [],
            },
            {
                "name": "JC Thomas",
                "hours": 25,
                "attendance_days": 4,
                "work_completed": ["Configured SSH and ROS."],
                "evidence_links": ["https://github.com/example/project"],
            },
        ],
        "checklist_status": {
            name: {
                "technical_portfolio": name == "JC Thomas",
                "updated_resume": name == "JC Thomas",
                "linkedin_profile_updated": False,
                "short_project_demonstration": False,
                "internship_or_employment_next_step": False,
            }
            for name in ["Javion Postell", "Rasheed Jeheeb", "Winston Doss", "Grayson Roper", "JC Thomas"]
        },
    }


def coursera():
    return {
        "schema_version": "1.0",
        "metrics": {"dashboard_total_learners": 16},
        "records": [{
            "normalized_name": "Javion Postell",
            "join_date": "2026-05-01",
            "candidate_person_id": "candidate:test",
        }],
    }


def test_baseline_summary_preserves_question_level_and_cohort_only_linkage():
    result = build_baseline_summary(baseline(), last_updated=UPDATED)
    assert result["question_count"] == 6
    assert result["all_responses_preserved"] is True
    assert result["question_level_processing"] is True
    assert result["person_level_linkage"]["linked_responses"] == 0
    assert result["person_level_linkage"]["identity_duplicates_detectable"] is False


def test_reporting_completeness_tracks_ahmed_without_adding_hours():
    result = build_reporting_completeness(week(), last_updated=UPDATED)
    assert result["metrics"]["expected_reports"]["value"] == 6
    assert result["metrics"]["submitted_reports"]["value"] == 5
    assert result["metrics"]["reporting_completion_percent"]["value"] == 83.33
    assert result["metrics"]["verified_hours"]["value"] == 78
    assert result["metrics"]["verified_participant_days"]["value"] == 19
    assert result["outstanding_students"][0]["student_id"] == "student:ahmed_h_kiel_kamil"


def test_submitted_incomplete_ahmed_report_closes_missing_report_but_not_verified_hours():
    supplement = {
        "student_id": "student:ahmed_h_kiel_kamil",
        "submitted": True,
        "approved": False,
        "submission_timestamp": None,
        "hours_reported": None,
        "evidence_count": 3,
        "missing_fields": ["submission_timestamp", "hours_reported", "attendance_days"],
        "source_blob_path": "raw/ahmed.docx",
        "activities": [],
    }
    result = build_reporting_completeness(
        week(), supplemental_reports=[supplement], last_updated=UPDATED
    )
    assert result["metrics"]["submitted_reports"]["value"] == 6
    assert result["metrics"]["missing_reports"]["value"] == 0
    assert result["metrics"]["approved_reports"]["value"] == 5
    assert result["metrics"]["verified_hours"]["value"] == 78
    assert result["outstanding_students"][0]["reason"] == "incomplete_report"


def test_narrative_is_not_treated_as_verified_artifact():
    activities = build_weekly_activities(week(), last_updated=UPDATED)
    with_evidence = next(item for item in activities if item["artifact_url"])
    narrative = next(item for item in activities if item["student_id"] == "student:winston_doss")
    assert with_evidence["verification_status"] == "evidence_submitted"
    assert narrative["verification_status"] == "reported_only"
    assert with_evidence["artifact_sha256"] is None


def test_longitudinal_and_coursera_unknowns_remain_pending_or_null():
    skills = build_skill_measurements(baseline(), last_updated=UPDATED)
    robotics = next(item for item in skills if item["competency_category"] == "robotics")
    assert robotics["baseline"]["self_assessment_score"] is None
    assert robotics["midpoint"]["evidence_status"] == "pending"
    assert robotics["baseline_to_final_change"] is None
    enhanced = enhance_coursera(coursera(), last_updated=UPDATED)
    assert enhanced["records"][0]["person_id"] == "student:javion_postell"
    assert enhanced["records"][0]["progress_percentage"] is None
    assert enhanced["records"][0]["certificate_verification"] is None


def test_student_outcomes_separates_indicators_and_proven_outcomes():
    result = build_student_outcomes(week(), baseline(), coursera(), last_updated=UPDATED)
    assert result["aggregate_metrics"]["verified_hours"]["evidence_status"] == "completed"
    assert result["aggregate_metrics"]["coursera_dashboard_learners"]["evidence_status"] == "evidence_submitted"
    assert result["sponsor_attribution"]["resources"][0]["outcomes_attributed"] == []
    assert result["github_evidence"]["verified_contributions"] == []
