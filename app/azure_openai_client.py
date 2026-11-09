from __future__ import annotations

import asyncio

from openai import AsyncAzureOpenAI

from app.config import Settings
from app.cloud_authorization import PaidJobApproval


class AzureOpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            max_retries=0,
        )

    async def brief(self, prompt: str, *, approval: PaidJobApproval | None = None) -> str:
        return await self.complete(
            "You are AARI Nexus Operator. Give concise, direct answers with no fluff.",
            prompt,
            max_tokens=300,
            approval=approval,
        )

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 450,
                       *, approval: PaidJobApproval | None = None) -> str:
        if not isinstance(approval, PaidJobApproval):
            raise PermissionError('Paid cloud inference requires explicit per-job operator approval')
        approval.consume(system_prompt, user_prompt, max_tokens, self.settings.azure_openai_deployment)
        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                temperature=0.2,
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": user_prompt},
                ],
            ),
            timeout=self.settings.model_timeout_seconds,
        )
        return response.choices[0].message.content or ""

    async def probe(self) -> dict[str, object]:
        # A status request is not permission to purchase even a one-token completion.
        return {'healthy': False, 'status_code': 403, 'deployment_found': False,
                'authorization_required': True}
