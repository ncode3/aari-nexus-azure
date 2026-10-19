"""Fail-closed policy for the prototype; this is not Entra authorization."""
from __future__ import annotations

from collections.abc import Mapping, Set


def telegram_chat_allowed(chat_id: int, allowed_chat_ids: Set[int]) -> bool:
    return chat_id in allowed_chat_ids


def prototype_api_allowed(environment: Mapping[str, str]) -> bool:
    # A deployed dev environment is not local. Never enable this in Container Apps.
    return (
        environment.get("APP_ENV", "").strip().lower() in {"local", "test"}
        and environment.get("NEXUS_LOCAL_EMAIL_PROTOTYPE", "").strip().lower() == "true"
    )
