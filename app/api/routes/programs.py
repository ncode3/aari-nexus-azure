import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.dependencies import pagination
from app.db.session import get_db
from app.models.entities import Cohorts, Grants, People, Students

router = APIRouter(tags=["programs"])


@router.get("/students")
def students(page: tuple[int, int] = Depends(pagination), db: Session = Depends(get_db)) -> dict:
    offset, limit = page
    statement = (
        select(Students, People)
        .join(People, People.id == Students.person_id)
        .where(Students.deleted_at.is_(None), People.deleted_at.is_(None))
        .offset(offset)
        .limit(limit)
    )
    items = [
        {
            "id": student.id,
            "student_number": student.student_number,
            "name": person.preferred_name or f"{person.first_name} {person.last_name}",
            "placement_status": student.placement_status,
        }
        for student, person in db.execute(statement)
    ]
    total = db.scalar(
        select(func.count()).select_from(Students).where(Students.deleted_at.is_(None))
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/students/{student_id}")
def student(student_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        select(Students, People)
        .join(People, People.id == Students.person_id)
        .where(Students.id == student_id, Students.deleted_at.is_(None))
    ).one_or_none()
    if not row:
        raise HTTPException(404, "Student not found")
    item, person = row
    return {
        "id": item.id,
        "student_number": item.student_number,
        "name": person.preferred_name or f"{person.first_name} {person.last_name}",
        "certification_goals": item.certification_goals,
        "placement_status": item.placement_status,
    }


@router.get("/students/{student_id}/progress")
def student_progress(student_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text("SELECT * FROM student_progress WHERE student_id = :student_id"),
        {"student_id": student_id},
    ).mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Student progress not found")
    return dict(row)


@router.get("/cohorts")
def cohorts(page: tuple[int, int] = Depends(pagination), db: Session = Depends(get_db)) -> dict:
    offset, limit = page
    items = list(
        db.scalars(
            select(Cohorts)
            .where(Cohorts.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
        )
    )
    total = db.scalar(
        select(func.count()).select_from(Cohorts).where(Cohorts.deleted_at.is_(None))
    )
    return {
        "items": [{"id": item.id, "slug": item.slug, "name": item.name} for item in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/cohorts/{cohort_id}")
def cohort(cohort_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    item = db.get(Cohorts, cohort_id)
    if not item or item.deleted_at:
        raise HTTPException(404, "Cohort not found")
    return {"id": item.id, "slug": item.slug, "name": item.name, "program_track": item.program_track}


@router.get("/cohorts/{cohort_id}/metrics")
def cohort_metrics(cohort_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text("SELECT * FROM cohort_metrics WHERE cohort_id = :cohort_id"),
        {"cohort_id": cohort_id},
    ).mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Cohort metrics not found")
    return dict(row)


@router.get("/grants")
def grants(page: tuple[int, int] = Depends(pagination), db: Session = Depends(get_db)) -> dict:
    offset, limit = page
    items = list(db.scalars(select(Grants).offset(offset).limit(limit)))
    total = db.scalar(select(func.count()).select_from(Grants))
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "award_amount": item.award_amount,
                "restricted": item.restricted,
                "status": item.status,
            }
            for item in items
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }

