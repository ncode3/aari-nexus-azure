import json
import uuid
from decimal import Decimal
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.readonly_database_url, pool_pre_ping=True)
mcp = FastMCP("AARI Read-Only Data")
MAX_RESULTS = 100


def _json_value(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    return value


def _rows(statement: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(text(statement), parameters).mappings()
        return [{key: _json_value(value) for key, value in row.items()} for row in rows]


def _audit(tool: str, *, success: bool = True, metadata: dict[str, Any] | None = None) -> None:
    request_id = str(uuid.uuid4())
    safe_metadata = {
        key: value
        for key, value in (metadata or {}).items()
        if key not in {"email", "phone", "content", "token", "password"}
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                SELECT log_mcp_audit(
                    :actor, :action, :entity_type, NULL, :request_id, :success,
                    CAST(:metadata AS jsonb)
                )
                """
            ),
            {
                "actor": "codex-mcp",
                "action": tool,
                "entity_type": "mcp_request",
                "request_id": request_id,
                "success": success,
                "metadata": json.dumps(safe_metadata),
            },
        )


def audited(tool: str, callback, metadata: dict[str, Any] | None = None):
    try:
        result = callback()
    except Exception:
        _audit(tool, success=False, metadata=metadata)
        raise
    _audit(tool, metadata=metadata)
    return result


@mcp.tool()
def search_people(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search active people with direct contact fields intentionally omitted."""
    limit = min(max(limit, 1), MAX_RESULTS)
    pattern = f"%{query[:200].replace('%', r'\%').replace('_', r'\_')}%"
    return audited(
        "search_people",
        lambda: _rows(
            """
            SELECT id, first_name, last_name, preferred_name, organization, title, active
            FROM people
            WHERE deleted_at IS NULL AND (
              first_name ILIKE :pattern ESCAPE '\\' OR
              last_name ILIKE :pattern ESCAPE '\\' OR
              organization ILIKE :pattern ESCAPE '\\'
            )
            ORDER BY last_name, first_name LIMIT :limit
            """,
            {"pattern": pattern, "limit": limit},
        ),
        {"limit": limit},
    )


@mcp.tool()
def get_student(student_id: str) -> list[dict[str, Any]]:
    """Get a student without direct contact details."""
    parsed = uuid.UUID(student_id)
    return audited(
        "get_student",
        lambda: _rows(
            """
            SELECT s.id, s.student_number, p.first_name, p.last_name, p.preferred_name,
                   s.certification_goals, s.placement_status
            FROM students s JOIN people p ON p.id = s.person_id
            WHERE s.id = :id AND s.deleted_at IS NULL
            """,
            {"id": parsed},
        ),
    )


@mcp.tool()
def get_student_progress(student_id: str) -> list[dict[str, Any]]:
    parsed = uuid.UUID(student_id)
    return audited(
        "get_student_progress",
        lambda: _rows("SELECT * FROM student_progress WHERE student_id = :id", {"id": parsed}),
    )


@mcp.tool()
def list_cohorts(limit: int = 50) -> list[dict[str, Any]]:
    limit = min(max(limit, 1), MAX_RESULTS)
    return audited(
        "list_cohorts",
        lambda: _rows(
            "SELECT id, slug, name, program_track, start_date, end_date "
            "FROM cohorts WHERE deleted_at IS NULL ORDER BY start_date DESC LIMIT :limit",
            {"limit": limit},
        ),
    )


@mcp.tool()
def get_cohort_metrics(cohort_id: str) -> list[dict[str, Any]]:
    parsed = uuid.UUID(cohort_id)
    return audited(
        "get_cohort_metrics",
        lambda: _rows("SELECT * FROM cohort_metrics WHERE cohort_id = :id", {"id": parsed}),
    )


@mcp.tool()
def search_documents(query: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = min(max(limit, 1), MAX_RESULTS)
    pattern = f"%{query[:200].replace('%', r'\%').replace('_', r'\_')}%"
    return audited(
        "search_documents",
        lambda: _rows(
            """
            SELECT id, original_filename, content_type, file_size, source_system,
                   processing_status, classification, ingested_at
            FROM documents
            WHERE deleted_at IS NULL
              AND classification <> 'restricted'
              AND original_filename ILIKE :pattern ESCAPE '\\'
            ORDER BY ingested_at DESC LIMIT :limit
            """,
            {"pattern": pattern, "limit": limit},
        ),
        {"limit": limit},
    )


@mcp.tool()
def get_document_metadata(document_id: str) -> list[dict[str, Any]]:
    parsed = uuid.UUID(document_id)
    return audited(
        "get_document_metadata",
        lambda: _rows(
            """
            SELECT id, original_filename, content_type, sha256, file_size, source_system,
                   source_url, ingested_at, processing_status, classification,
                   retention_category, current_version, metadata
            FROM documents
            WHERE id = :id AND deleted_at IS NULL AND classification <> 'restricted'
            """,
            {"id": parsed},
        ),
    )


@mcp.tool()
def search_document_chunks(query: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = min(max(limit, 1), MAX_RESULTS)
    pattern = f"%{query[:200].replace('%', r'\%').replace('_', r'\_')}%"
    return audited(
        "search_document_chunks",
        lambda: _rows(
            """
            SELECT dc.document_id, dc.chunk_sequence, dc.page_number, dc.section_heading,
                   left(dc.text_content, 1000) AS excerpt
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.classification <> 'restricted'
              AND dc.text_content ILIKE :pattern ESCAPE '\\'
            ORDER BY dc.document_id, dc.chunk_sequence LIMIT :limit
            """,
            {"pattern": pattern, "limit": limit},
        ),
        {"limit": limit},
    )


@mcp.tool()
def get_grant_status(grant_id: str) -> list[dict[str, Any]]:
    parsed = uuid.UUID(grant_id)
    return audited(
        "get_grant_status",
        lambda: _rows(
            """
            SELECT id, name, award_amount, restricted, start_date, end_date, status
            FROM grants WHERE id = :id AND deleted_at IS NULL
            """,
            {"id": parsed},
        ),
    )


@mcp.tool()
def get_financial_summary() -> list[dict[str, Any]]:
    return audited(
        "get_financial_summary",
        lambda: _rows(
            "SELECT * FROM financial_summary ORDER BY currency, fund_restriction", {}
        ),
    )


@mcp.tool()
def get_workflow_run(workflow_run_id: str) -> list[dict[str, Any]]:
    parsed = uuid.UUID(workflow_run_id)
    return audited(
        "get_workflow_run",
        lambda: _rows(
            """
            SELECT id, workflow_type, status, import_batch_id, started_at, completed_at,
                   records_discovered, records_processed, records_rejected, error_summary
            FROM workflow_runs WHERE id = :id
            """,
            {"id": parsed},
        ),
    )


if __name__ == "__main__":
    mcp.run()
