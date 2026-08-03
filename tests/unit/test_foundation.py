from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


def test_health_is_credentials_free() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


def test_redis_is_not_required() -> None:
    settings = Settings(_env_file=None)
    assert not hasattr(settings, "redis_url")


def test_cors_disabled_by_default() -> None:
    assert Settings(_env_file=None).cors_origins == []

