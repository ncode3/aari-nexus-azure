import hashlib
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assessment_flow import AssessmentMetadata, normalize_rows
from app.models.entities import (
    AssessmentQuestions,
    AssessmentResponses,
    Assessments,
    Cohorts,
    FinancialAccounts,
    People,
    Students,
    Transactions,
)


def transaction_fingerprint(
    account_id: uuid.UUID | str,
    transaction_date: date,
    amount: Decimal,
    description: str,
) -> str:
    canonical = "|".join(
        [
            str(account_id),
            transaction_date.isoformat(),
            format(amount.quantize(Decimal("0.01")), "f"),
            " ".join(description.lower().split()),
        ]
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def import_financial_rows(
    session: Session,
    rows: list[dict[str, Any]],
    *,
    account: FinancialAccounts,
    import_batch_id: str,
) -> tuple[int, int]:
    inserted = duplicates = 0
    for index, row in enumerate(rows, start=2):
        try:
            transaction_date = date.fromisoformat(str(row["date"]).strip())
            amount = Decimal(str(row["amount"]).replace(",", "").strip())
            description = str(row["description"]).strip()
        except (KeyError, InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid financial row {index}: {exc}") from exc
        if not description:
            raise ValueError(f"Invalid financial row {index}: description is required")
        fingerprint = transaction_fingerprint(
            account.id, transaction_date, amount, description
        )
        if session.scalar(select(Transactions.id).where(Transactions.fingerprint == fingerprint)):
            duplicates += 1
            continue
        session.add(
            Transactions(
                financial_account_id=account.id,
                transaction_date=transaction_date,
                description=description,
                vendor=str(row.get("vendor") or "").strip() or None,
                amount=amount,
                currency=str(row.get("currency") or "USD").upper(),
                fund_restriction=str(row.get("fund_restriction") or "unrestricted"),
                reconciliation_status=str(row.get("reconciliation_status") or "unreconciled"),
                import_batch_id=import_batch_id,
                fingerprint=fingerprint,
                metadata_json={},
            )
        )
        inserted += 1
    session.flush()
    return inserted, duplicates


def import_student_roster(
    session: Session, rows: list[dict[str, Any]], *, cohort: Cohorts | None = None
) -> tuple[int, int]:
    inserted = existing = 0
    for index, row in enumerate(rows, start=2):
        email = str(row.get("primary_email") or row.get("email") or "").strip().lower()
        student_number = str(row.get("student_number") or "").strip() or None
        if not email and not student_number:
            raise ValueError(f"Invalid roster row {index}: email or student_number is required")
        person = session.scalar(select(People).where(People.primary_email == email)) if email else None
        student = None
        if person:
            student = session.scalar(select(Students).where(Students.person_id == person.id))
        if student_number and not student:
            student = session.scalar(
                select(Students).where(Students.student_number == student_number)
            )
        if student:
            existing += 1
            continue
        person = person or People(
            first_name=str(row.get("first_name") or "").strip(),
            last_name=str(row.get("last_name") or "").strip(),
            preferred_name=str(row.get("preferred_name") or "").strip() or None,
            primary_email=email or None,
            organization=str(row.get("organization") or "").strip() or None,
            external_identifiers={},
            active=True,
        )
        if not person.first_name or not person.last_name:
            raise ValueError(f"Invalid roster row {index}: first_name and last_name are required")
        session.add(person)
        session.flush()
        session.add(
            Students(
                person_id=person.id,
                student_number=student_number,
                certification_goals=[],
                employment_outcomes={},
            )
        )
        inserted += 1
    session.flush()
    return inserted, existing


QUESTION_MAP = {
    "linux_experience_level": ("linux", "number"),
    "command_line_experience_level": ("command_line", "number"),
    "public_cloud_experience": ("cloud", "boolean"),
    "server_build_experience": ("server_hardware", "boolean"),
    "networking_familiarity": ("networking", "boolean"),
    "job_market_ready": ("career_readiness", "boolean"),
}


def import_technical_assessment(
    session: Session,
    rows: list[dict[str, Any]],
    metadata: AssessmentMetadata,
    *,
    cohort: Cohorts,
    source_document_id: uuid.UUID,
) -> tuple[Assessments, int]:
    package = normalize_rows(rows, metadata)
    assessment = session.scalar(
        select(Assessments).where(
            Assessments.source_document_id == source_document_id,
            Assessments.stage == metadata.assessment_stage,
        )
    )
    if assessment:
        count = session.scalar(
            select(func.count())
            .select_from(AssessmentResponses)
            .where(AssessmentResponses.assessment_id == assessment.id)
        )
        return assessment, int(count or 0)
    assessment = Assessments(
        name="AARI Technical Skills Assessment",
        assessment_type="technical_skills_survey",
        stage=metadata.assessment_stage,
        instrument_version=metadata.instrument_version,
        cohort_id=cohort.id,
        source_document_id=source_document_id,
        assessment_date=datetime.fromisoformat(
            package["assessment_window"]["start"]
        ).date(),
        metadata_json={
            "linkage_mode": package["linkage_mode"],
            "aggregate": package["aggregate"],
        },
    )
    session.add(assessment)
    session.flush()
    questions: dict[str, AssessmentQuestions] = {}
    for sequence, (field, (competency, response_type)) in enumerate(
        QUESTION_MAP.items(), start=1
    ):
        question = AssessmentQuestions(
            assessment_id=assessment.id,
            question_key=field,
            prompt=field.replace("_", " ").title(),
            response_type=response_type,
            competency=competency,
            max_score=Decimal("5") if response_type == "number" else Decimal("1"),
            sequence=sequence,
        )
        session.add(question)
        questions[field] = question
    session.flush()
    for record in package["responses"]:
        for field, question in questions.items():
            value = record[field]
            session.add(
                AssessmentResponses(
                    assessment_id=assessment.id,
                    question_id=question.id,
                    student_id=None,
                    response_identifier=record["response_id"],
                    submitted_at=datetime.fromisoformat(record["submitted_at"]),
                    response_text=str(value),
                    response_number=Decimal(str(int(value) if isinstance(value, bool) else value)),
                    response_json={"linkage_status": record["linkage_status"]},
                )
            )
    session.flush()
    return assessment, len(package["responses"])
