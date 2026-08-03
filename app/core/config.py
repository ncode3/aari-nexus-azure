from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://aari_app:local-app-change-me@localhost:5432/aari"
    database_admin_url: str | None = None
    readonly_database_url: str = (
        "postgresql+psycopg://aari_readonly:local-readonly-change-me@localhost:5432/aari"
    )
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "aari_app"
    minio_secret_key: str = ""
    minio_secure: bool = False
    minio_documents_bucket: str = "aari-documents"
    minio_rejected_bucket: str = "aari-rejected"
    max_upload_bytes: int = 50 * 1024 * 1024
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/json",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "text/plain",
        ]
    )
    cors_origins: list[str] = Field(default_factory=list)
    enable_telegram_bot: bool = False
    embedding_provider: str = "disabled"
    embedding_dimensions: int = 1536
    api_page_size: int = 50
    api_max_page_size: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
