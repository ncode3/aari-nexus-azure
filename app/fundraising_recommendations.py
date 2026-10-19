"""Deterministic recommendation contract over already authorized, reviewed rows.

Not a live SQL integration. Do not expose this as an API until caller authorization,
SQL connectivity and source ACLs pass the staging gate. No model or network calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Evidence:
    reference: str
    tenant_id: str
    scope_key: str
    observed_on: date
    approved: bool


@dataclass(frozen=True)
class Approach:
    organization: str
    tenant_id: str
    scope_key: str
    reviewed_priority: int
    next_action: str
    action_kind: str
    contact: str | None
    proposed_amount: Decimal | None
    currency: str
    blockers: tuple[str, ...]
    evidence: Evidence
    budget_controller: str | None = None
    budget_authority_evidence: Evidence | None = None
    rejected: bool = False
    approved: bool = False


def recommend_next(
    approaches: list[Approach], *, tenant_id: str, allowed_scopes: frozenset[str],
    as_of: date, max_age_days: int = 90,
) -> dict:
    """Accept scopes from a trusted authorization layer, never user query params.

    Human-reviewed priorities determine ranking; an LLM must not invent priorities,
    amounts or budget authority. Blocked applications permit discovery, not submission.
    """
    if max_age_days < 0:
        raise ValueError("max_age_days must not be negative")

    def usable(evidence: Evidence, row: Approach) -> bool:
        age = (as_of - evidence.observed_on).days
        return (
            evidence.approved and bool(evidence.reference.strip())
            and evidence.tenant_id == tenant_id == row.tenant_id
            and evidence.scope_key == row.scope_key
            and evidence.scope_key in allowed_scopes and 0 <= age <= max_age_days
        )

    candidates = [row for row in approaches if (
        row.approved and not row.rejected and row.reviewed_priority > 0 and usable(row.evidence, row)
        and row.action_kind in {"DISCOVERY", "SUBMISSION", "FOLLOW_UP"}
        and bool(row.next_action.strip())
        and (not row.blockers or row.action_kind == "DISCOVERY")
    )]
    if not candidates:
        return {"status": "insufficient_evidence", "as_of": as_of.isoformat(),
                "recommendation": None, "evidence": []}
    row = min(candidates, key=lambda r: (r.reviewed_priority, r.organization.casefold()))
    authority = row.budget_authority_evidence
    authority_known = bool(row.budget_controller and authority and usable(authority, row))
    amount = row.proposed_amount
    amount_known = amount is not None and amount.is_finite() and amount > 0
    sources = [row.evidence.reference]
    if authority_known and authority.reference not in sources:
        sources.append(authority.reference)
    unknowns = []
    if not authority_known:
        unknowns.append("Budget controller and approval authority are not established by evidence.")
    if not amount_known:
        unknowns.append("Request amount is not established by evidence.")
    return {
        "status": "recommendation_with_unknowns" if unknowns or row.blockers else "reviewed_recommendation",
        "as_of": as_of.isoformat(),
        "recommendation": {
            "approach": row.organization, "contact": row.contact,
            "next_action": row.next_action, "action_kind": row.action_kind,
            "request": {"amount": str(amount) if amount_known else None,
                        "currency": row.currency, "state": "PROPOSED"},
            "budget_controller": row.budget_controller if authority_known else None,
            "budget_controller_status": "evidence_supported" if authority_known else "unknown",
            "blockers": list(row.blockers),
        },
        "evidence": sources, "unknowns": unknowns,
        "basis": "Human-reviewed priority over authorized evidence; not an award or spending commitment.",
    }
