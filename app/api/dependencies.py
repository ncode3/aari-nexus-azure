from fastapi import Query

from app.core.config import get_settings


def pagination(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1),
) -> tuple[int, int]:
    settings = get_settings()
    return offset, min(limit, settings.api_max_page_size)

