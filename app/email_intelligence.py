"""Read-only, evidence-backed funding dashboard data. No Gmail credentials required."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "business-intelligence" / "verified-funding-2026-10-13.json"

def build_funding_dashboard(path: str | Path = DEFAULT_DATA) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data["records"]
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    awarded = sum(int(r.get("awarded_usd") or 0) for r in records if r.get("stage") == "awarded")
    received_verified = sum(int(r.get("received_usd") or 0) for r in records if r.get("received_verified") is True)
    goal = int(data["goal_usd"])
    return {
        "as_of": data["as_of"],
        "goal_usd": goal,
        "verified_awarded_usd": awarded,
        "verified_received_usd": received_verified,
        "remaining_to_goal_awarded_usd": max(0, goal - awarded),
        "opportunities": records,
        "warning": "Awarded and received are separate; missing receipt verification is not proof of nonpayment.",
    }
