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
    deposited_confirmed = sum(int(r.get("deposited_usd") or 0) for r in records
                              if r.get("deposited_confirmed") is True
                              and r.get("deposit_evidence_kind") in {"EXECUTIVE_CONFIRMATION", "BANK_RECONCILIATION"})
    reconciled = [int(r.get("bank_reconciled_usd") or 0) for r in records
                  if r.get("bank_reconciled_verified") is True
                  and r.get("bank_reconciliation_evidence_kind") == "BANK_RECONCILIATION"
                  and r.get("bank_reconciliation_evidence")]
    goal = int(data["goal_usd"])
    return {
        "as_of": data["as_of"],
        "goal_usd": goal,
        "verified_awarded_usd": awarded,
        "verified_received_usd": received_verified,
        "confirmed_deposited_usd": deposited_confirmed,
        "bank_reconciled_usd": sum(reconciled) if reconciled else None,
        "bank_reconciliation_status": "evidence_present" if reconciled else "unknown",
        "remaining_to_goal_awarded_usd": max(0, goal - awarded),
        "opportunities": records,
        "warning": "Awarded, received and deposited are separate totals, never added together. Executive deposit confirmation is not independent bank reconciliation.",
    }
