from __future__ import annotations

import httpx

from app.config import Settings


class PepClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.pep_base_url.rstrip("/")
        self.health_timeout_seconds = settings.pep_health_timeout_seconds

    async def health_check(self) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=self.health_timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
            return {
                "status": "healthy",
                "healthy": True,
                "base_url": self.base_url,
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "healthy": False,
                "base_url": self.base_url,
                "error": type(exc).__name__,
            }
