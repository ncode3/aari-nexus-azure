import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Page(BaseModel):
    items: list[dict[str, Any]]
    total: int
    offset: int
    limit: int


class DocumentOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    sha256: str
    file_size: int
    source_system: str
    processing_status: str
    classification: str
    ingested_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionJobRequest(BaseModel):
    source_system: str = Field(min_length=1, max_length=100)
    source_identifier: str = Field(min_length=1, max_length=500)
    classification: str = Field(default="internal", pattern="^(public|internal|restricted)$")
    metadata: dict[str, Any] = Field(default_factory=dict)

