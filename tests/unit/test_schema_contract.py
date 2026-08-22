import app.models  # noqa: F401
from app.db.base import Base
from app.main import app


def test_all_required_tables_are_declared() -> None:
    required = {
        "people",
        "students",
        "cohorts",
        "cohort_memberships",
        "attendance_records",
        "assessments",
        "assessment_questions",
        "assessment_responses",
        "certifications",
        "student_certifications",
        "platform_activity",
        "projects",
        "project_members",
        "equipment",
        "equipment_assignments",
        "partners",
        "partner_contacts",
        "grants",
        "grant_activities",
        "financial_accounts",
        "transactions",
        "transaction_categories",
        "documents",
        "document_versions",
        "document_chunks",
        "workflow_runs",
        "ingestion_events",
        "audit_events",
    }
    assert required == set(Base.metadata.tables)


def test_required_api_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    required = {
        "/health",
        "/ready",
        "/api/v1/documents",
        "/api/v1/documents/{document_id}",
        "/api/v1/ingestion/jobs",
        "/api/v1/ingestion/jobs/{job_id}",
        "/api/v1/students",
        "/api/v1/students/{student_id}",
        "/api/v1/students/{student_id}/progress",
        "/api/v1/cohorts",
        "/api/v1/cohorts/{cohort_id}",
        "/api/v1/cohorts/{cohort_id}/metrics",
        "/api/v1/grants",
        "/api/v1/financial/summary",
        "/api/v1/search",
    }
    assert required <= set(paths)
