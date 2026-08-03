import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Documents
from app.repositories.base import Repository


class DocumentRepository(Repository[Documents]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Documents)

    def by_checksum(self, sha256: str) -> Documents | None:
        return self.session.scalar(select(Documents).where(Documents.sha256 == sha256))

    def search(self, query: str, *, offset: int = 0, limit: int = 50) -> list[Documents]:
        safe = query.replace("%", r"\%").replace("_", r"\_")
        statement = select(Documents).where(
            Documents.original_filename.ilike(f"%{safe}%", escape="\\"),
            Documents.deleted_at.is_(None),
        )
        return self.page(offset=offset, limit=limit, statement=statement)

    def get_active(self, entity_id: uuid.UUID) -> Documents | None:
        return self.session.scalar(
            select(Documents).where(Documents.id == entity_id, Documents.deleted_at.is_(None))
        )

