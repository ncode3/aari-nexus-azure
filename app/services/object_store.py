from io import BytesIO
from typing import Protocol

from minio import Minio

from app.core.config import Settings, get_settings


class ObjectStore(Protocol):
    def put(self, bucket: str, key: str, content: bytes, content_type: str) -> None: ...

    def exists(self, bucket: str, key: str) -> bool: ...


class MinioObjectStore:
    def __init__(self, settings: Settings | None = None) -> None:
        config = settings or get_settings()
        self.client = Minio(
            config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key,
            secure=config.minio_secure,
        )

    def put(self, bucket: str, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            bucket,
            key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.stat_object(bucket, key)
        except Exception as exc:
            if getattr(exc, "code", "") in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise
        return True

