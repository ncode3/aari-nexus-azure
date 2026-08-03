from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import (
    CohortMemberships,
    Cohorts,
    FinancialAccounts,
    Grants,
    People,
    Students,
)


def main() -> None:
    with SessionLocal.begin() as session:
        cohort = session.scalar(select(Cohorts).where(Cohorts.slug == "demo-data-center"))
        if not cohort:
            cohort = Cohorts(
                slug="demo-data-center",
                name="Demo Data Center Cohort",
                program_track="data-center",
                metadata_json={"demo": True},
            )
            session.add(cohort)
            session.flush()
        person = session.scalar(select(People).where(People.primary_email == "demo@example.invalid"))
        if not person:
            person = People(
                first_name="Demo",
                last_name="Student",
                primary_email="demo@example.invalid",
                external_identifiers={},
            )
            session.add(person)
            session.flush()
            student = Students(
                person_id=person.id,
                student_number="DEMO-001",
                certification_goals=["Linux"],
                employment_outcomes={},
            )
            session.add(student)
            session.flush()
            session.add(CohortMemberships(cohort_id=cohort.id, student_id=student.id))
        if not session.scalar(select(Grants).where(Grants.external_identifier == "DEMO-GRANT")):
            session.add(
                Grants(
                    name="Demo Workforce Grant",
                    external_identifier="DEMO-GRANT",
                    award_amount=Decimal("25000.00"),
                    restricted=True,
                    status="active",
                )
            )
        if not session.scalar(
            select(FinancialAccounts).where(FinancialAccounts.masked_identifier == "DEMO-0001")
        ):
            session.add(
                FinancialAccounts(
                    name="Demo Operating",
                    account_type="checking",
                    masked_identifier="DEMO-0001",
                )
            )
    print("Demo student, cohort, grant, and financial account are ready.")


if __name__ == "__main__":
    main()

