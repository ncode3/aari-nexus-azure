import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UUIDTimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class People(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "people"
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(100))
    primary_email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    organization: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(200))
    external_identifiers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Students(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "students"
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    student_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    certification_goals: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    placement_status: Mapped[str | None] = mapped_column(String(60))
    employment_outcomes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Cohorts(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "cohorts"
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    program_track: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class CohortMemberships(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "cohort_memberships"
    __table_args__ = (UniqueConstraint("cohort_id", "student_id"),)
    cohort_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cohorts.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    enrollment_status: Mapped[str] = mapped_column(String(40), default="enrolled")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    hourly_pay: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    stipend_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class AttendanceRecords(UUIDTimestampMixin, Base):
    __tablename__ = "attendance_records"
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    cohort_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cohorts.id"), nullable=False)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="present")
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    __table_args__ = (
        UniqueConstraint("student_id", "cohort_id", "attendance_date"),
        CheckConstraint("hours >= 0 AND hours <= 24", name="valid_hours"),
    )


class Documents(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    minio_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processing_status: Mapped[str] = mapped_column(String(40), default="pending")
    classification: Mapped[str] = mapped_column(String(40), default="internal")
    retention_category: Mapped[str] = mapped_column(String(100), default="program_record")
    created_by_person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    __table_args__ = (
        CheckConstraint("file_size >= 0", name="nonnegative_size"),
        CheckConstraint("current_version >= 1", name="valid_current_version"),
    )


class DocumentVersions(UUIDTimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class Assessments(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "assessments"
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    instrument_version: Mapped[str | None] = mapped_column(String(50))
    cohort_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cohorts.id"))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    assessment_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class AssessmentQuestions(UUIDTimestampMixin, Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (UniqueConstraint("assessment_id", "question_key"),)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), nullable=False)
    question_key: Mapped[str] = mapped_column(String(150), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_type: Mapped[str] = mapped_column(String(30), nullable=False)
    competency: Mapped[str | None] = mapped_column(String(100))
    max_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)


class AssessmentResponses(UUIDTimestampMixin, Base):
    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_id", "response_identifier"),
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_questions.id"), nullable=False
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"))
    response_identifier: Mapped[str] = mapped_column(String(150), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_text: Mapped[str | None] = mapped_column(Text)
    response_number: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Certifications(UUIDTimestampMixin, Base):
    __tablename__ = "certifications"
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    issuing_organization: Mapped[str] = mapped_column(String(200), nullable=False)
    external_code: Mapped[str | None] = mapped_column(String(100), unique=True)


class StudentCertifications(UUIDTimestampMixin, Base):
    __tablename__ = "student_certifications"
    __table_args__ = (UniqueConstraint("student_id", "certification_id", "issued_date"),)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    certification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("certifications.id"), nullable=False
    )
    issued_date: Mapped[date | None] = mapped_column(Date)
    expires_date: Mapped[date | None] = mapped_column(Date)
    credential_identifier: Mapped[str | None] = mapped_column(String(200))
    verification_status: Mapped[str] = mapped_column(String(40), default="unverified")
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


class PlatformActivity(UUIDTimestampMixin, Base):
    __tablename__ = "platform_activity"
    __table_args__ = (UniqueConstraint("source_system", "external_activity_id"),)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"))
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    external_activity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class Projects(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active")
    cohort_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cohorts.id"))


class ProjectMembers(UUIDTimestampMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "person_id"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    joined_at: Mapped[date | None] = mapped_column(Date)
    left_at: Mapped[date | None] = mapped_column(Date)


class Equipment(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "equipment"
    asset_tag: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="available")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class EquipmentAssignments(UUIDTimestampMixin, Base):
    __tablename__ = "equipment_assignments"
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    condition_notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "person_id IS NOT NULL OR project_id IS NOT NULL", name="assignment_target"
        ),
    )


class Partners(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "partners"
    name: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    partner_type: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PartnerContacts(UUIDTimestampMixin, Base):
    __tablename__ = "partner_contacts"
    __table_args__ = (UniqueConstraint("partner_id", "person_id"),)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"), nullable=False)
    role: Mapped[str | None] = mapped_column(String(150))
    primary_contact: Mapped[bool] = mapped_column(Boolean, default=False)


class Grants(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "grants"
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    grantor_partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id"))
    external_identifier: Mapped[str | None] = mapped_column(String(150), unique=True)
    award_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="proposed")
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


class GrantActivities(UUIDTimestampMixin, Base):
    __tablename__ = "grant_activities"
    grant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grants.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    cohort_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cohorts.id"))
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[date | None] = mapped_column(Date)
    amount_attributed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class FinancialAccounts(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "financial_accounts"
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    account_type: Mapped[str] = mapped_column(String(100), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(200))
    masked_identifier: Mapped[str | None] = mapped_column(String(50), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TransactionCategories(UUIDTimestampMixin, Base):
    __tablename__ = "transaction_categories"
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transaction_categories.id"))
    category_type: Mapped[str] = mapped_column(String(30), nullable=False)


class Transactions(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "transactions"
    financial_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("financial_accounts.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transaction_categories.id"))
    grant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("grants.id"))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(250))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    fund_restriction: Mapped[str] = mapped_column(String(30), default="unrestricted")
    reconciliation_status: Mapped[str] = mapped_column(String(40), default="unreconciled")
    import_batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class DocumentChunks(UUIDTimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_version_id", "chunk_sequence"),)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id"), nullable=False
    )
    chunk_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_heading: Mapped[str | None] = mapped_column(String(500))
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class WorkflowRuns(UUIDTimestampMixin, Base):
    __tablename__ = "workflow_runs"
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    import_batch_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_discovered: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class IngestionEvents(UUIDTimestampMixin, Base):
    __tablename__ = "ingestion_events"
    __table_args__ = (UniqueConstraint("source_system", "source_identifier", "event_type"),)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class AuditEvents(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    request_id: Mapped[str | None] = mapped_column(String(100))
    source_ip: Mapped[str | None] = mapped_column(String(64))
    before_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


Index("ix_people_name", People.last_name, People.first_name)
Index("ix_attendance_cohort_date", AttendanceRecords.cohort_id, AttendanceRecords.attendance_date)
Index("ix_documents_classification_status", Documents.classification, Documents.processing_status)
Index("ix_assessment_responses_student", AssessmentResponses.student_id)
Index("ix_platform_activity_student_date", PlatformActivity.student_id, PlatformActivity.activity_at)
Index("ix_transactions_date", Transactions.transaction_date)
Index("ix_audit_entity", AuditEvents.entity_type, AuditEvents.entity_id)
Index("ix_document_chunks_document", DocumentChunks.document_id, DocumentChunks.chunk_sequence)
