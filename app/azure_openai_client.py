from __future__ import annotations

import asyncio

from openai import AsyncAzureOpenAI

from app.config import Settings


class AzureOpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )

    async def brief(self, prompt: str) -> str:
        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                temperature=0.2,
                max_tokens=300,
                messages=[
                    {
                        "role": "system",
                        "content": "You are AARI Nexus Operator. Give concise, direct answers with no fluff.",
                    },
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=self.settings.model_timeout_seconds,
        )
        return response.choices[0].message.content or ""

    async def probe(self) -> dict[str, object]:
        try:
            await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.settings.azure_openai_deployment,
                    temperature=0,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                ),
                timeout=self.settings.model_timeout_seconds,
            )
            return {
                "healthy": True,
                "status_code": 200,
                "deployment_found": True,
            }
        except Exception as exc:
            status_code = getattr(exc, "status_code", None) or 500
            return {
                "healthy": False,
                "status_code": status_code,
                "deployment_found": status_code != 404,
            }
