from __future__ import annotations

import sys

from minio import Minio
from sqlalchemy import create_engine, text

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    checks: dict[str, bool] = {}
    with create_engine(settings.database_url, pool_pre_ping=True).connect() as connection:
        checks["postgresql"] = connection.scalar(text("SELECT 1")) == 1
        checks["pgvector"] = bool(
            connection.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        )
    minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    buckets = {item.name for item in minio.list_buckets()}
    checks["documents_bucket"] = settings.minio_documents_bucket in buckets
    checks["rejected_bucket"] = settings.minio_rejected_bucket in buckets
    for name, passed in checks.items():
        print(f"{name}: {'ok' if passed else 'failed'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

