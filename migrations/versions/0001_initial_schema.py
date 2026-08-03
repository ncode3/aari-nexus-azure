"""Create the portable AARI schema and reporting views."""

from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind, checkfirst=True)
    op.execute(
        """
        CREATE OR REPLACE VIEW student_progress AS
        SELECT s.id AS student_id,
               p.first_name,
               p.last_name,
               COUNT(DISTINCT ar.attendance_date) AS attendance_days,
               COALESCE(SUM(ar.hours), 0)::numeric(12,2) AS attendance_hours,
               COUNT(DISTINCT sc.id) AS certifications,
               COUNT(DISTINCT pa.id) AS platform_activities
        FROM students s
        JOIN people p ON p.id = s.person_id
        LEFT JOIN attendance_records ar ON ar.student_id = s.id
        LEFT JOIN student_certifications sc ON sc.student_id = s.id
        LEFT JOIN platform_activity pa ON pa.student_id = s.id
        WHERE s.deleted_at IS NULL AND p.deleted_at IS NULL
        GROUP BY s.id, p.first_name, p.last_name
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION log_mcp_audit(
            p_actor text,
            p_action text,
            p_entity_type text,
            p_entity_id uuid,
            p_request_id text,
            p_success boolean,
            p_metadata jsonb
        ) RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE v_id uuid := gen_random_uuid();
        BEGIN
            INSERT INTO audit_events(
                id, actor, action, entity_type, entity_id, occurred_at,
                request_id, success, metadata
            ) VALUES (
                v_id, left(p_actor, 200), left(p_action, 100),
                left(p_entity_type, 100), p_entity_id, now(),
                left(p_request_id, 100), p_success,
                COALESCE(p_metadata, '{}'::jsonb)
            );
            RETURN v_id;
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION log_mcp_audit(text,text,text,uuid,text,boolean,jsonb) FROM PUBLIC")
    op.execute(
        """
        CREATE OR REPLACE VIEW cohort_metrics AS
        SELECT c.id AS cohort_id,
               c.slug,
               c.name,
               COUNT(DISTINCT cm.student_id) AS enrolled_students,
               COUNT(DISTINCT ar.attendance_date) AS attendance_days,
               COALESCE(SUM(ar.hours), 0)::numeric(12,2) AS attendance_hours
        FROM cohorts c
        LEFT JOIN cohort_memberships cm
          ON cm.cohort_id = c.id AND cm.deleted_at IS NULL
        LEFT JOIN attendance_records ar
          ON ar.cohort_id = c.id
        WHERE c.deleted_at IS NULL
        GROUP BY c.id, c.slug, c.name
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW financial_summary AS
        SELECT currency,
               fund_restriction,
               COALESCE(SUM(amount), 0)::numeric(14,2) AS net_amount,
               COUNT(*) AS transaction_count
        FROM transactions
        WHERE deleted_at IS NULL
        GROUP BY currency, fund_restriction
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP VIEW IF EXISTS financial_summary")
    op.execute("DROP VIEW IF EXISTS cohort_metrics")
    op.execute("DROP VIEW IF EXISTS student_progress")
    op.execute(
        "DROP FUNCTION IF EXISTS log_mcp_audit(text,text,text,uuid,text,boolean,jsonb)"
    )
    Base.metadata.drop_all(bind=bind, checkfirst=True)
