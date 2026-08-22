import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.base import Base


class Repository[ModelT: Base]:
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def page(self, *, offset: int = 0, limit: int = 50, statement: Select | None = None):
        query = statement if statement is not None else select(self.model)
        return list(self.session.scalars(query.offset(offset).limit(limit)))

    def count(self, statement: Select | None = None) -> int:
        query = statement if statement is not None else select(self.model)
        return int(self.session.scalar(select(func.count()).select_from(query.subquery())) or 0)
