from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.entities import People
from app.repositories.base import Repository


class PeopleRepository(Repository[People]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, People)

    def search(self, query: str, limit: int = 50) -> list[People]:
        safe = query.replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{safe}%"
        statement = select(People).where(
            People.deleted_at.is_(None),
            or_(
                People.first_name.ilike(pattern, escape="\\"),
                People.last_name.ilike(pattern, escape="\\"),
                People.preferred_name.ilike(pattern, escape="\\"),
                People.organization.ilike(pattern, escape="\\"),
            ),
        )
        return self.page(limit=limit, statement=statement)

