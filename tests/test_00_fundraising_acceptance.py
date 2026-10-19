"""First business acceptance case: next approach, ask, authority, evidence.

Offline contract only. Source: PR #29 curated seed/specification; not mailbox access.
The priority is a review proposal, not a fact contained in the source email.
"""
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

from app.fundraising_recommendations import Approach, Evidence, recommend_next

AS_OF = date(2026, 10, 13)
SOURCE = "PR29 seed truist-equipment-2026; Gmail message 1a1305a1e5db5d63 (link unverified)"


class FirstBusinessAcceptance(unittest.TestCase):
    def setUp(self):
        self.source = Evidence(SOURCE, "aari", "fundraising", AS_OF, True)
        self.truist = Approach(
            organization="Truist Trusteed Foundations", tenant_id="aari", scope_key="fundraising",
            reviewed_priority=1, next_action="Speak with Kristina Christy before applying; ask who controls and approves the equipment budget.",
            action_kind="DISCOVERY", contact="Kristina Christy", proposed_amount=Decimal("100000"),
            currency="USD", blockers=("Resolve one-year operating history eligibility.", "Provide board-member list."),
            evidence=self.source, approved=True,
        )

    def answer(self, rows=None, scopes=frozenset({"fundraising"})):
        return recommend_next([self.truist] if rows is None else rows, tenant_id="aari", allowed_scopes=scopes, as_of=AS_OF)

    def test_00_who_next_how_much_budget_authority_and_evidence(self):
        result = self.answer()
        self.assertEqual(result["recommendation"]["approach"], "Truist Trusteed Foundations")
        self.assertEqual(result["recommendation"]["contact"], "Kristina Christy")
        self.assertEqual(result["recommendation"]["request"], {"amount": "100000", "currency": "USD", "state": "PROPOSED"})
        self.assertIsNone(result["recommendation"]["budget_controller"])
        self.assertEqual(result["recommendation"]["budget_controller_status"], "unknown")
        self.assertEqual(result["evidence"], [SOURCE])
        self.assertEqual(result["recommendation"]["action_kind"], "DISCOVERY")
        self.assertEqual(len(result["recommendation"]["blockers"]), 2)

    def test_contact_is_not_budget_authority_without_separate_evidence(self):
        result = self.answer([replace(self.truist, budget_controller="Kristina Christy")])
        self.assertIsNone(result["recommendation"]["budget_controller"])

    def test_verified_authority_has_its_own_citation(self):
        source = replace(self.source, reference="synthetic authority evidence")
        result = self.answer([replace(self.truist, budget_controller="Synthetic budget committee", budget_authority_evidence=source)])
        self.assertEqual(result["recommendation"]["budget_controller"], "Synthetic budget committee")
        self.assertIn("synthetic authority evidence", result["evidence"])

    def test_no_authorized_evidence_does_not_leak_a_candidate(self):
        self.assertEqual(self.answer(scopes=frozenset())["status"], "insufficient_evidence")
        other_tenant = replace(self.truist, tenant_id="other")
        self.assertIsNone(self.answer([other_tenant])["recommendation"])

    def test_cross_scope_authority_is_not_retrieved(self):
        authority = replace(self.source, reference="private authority evidence", scope_key="restricted")
        result = self.answer([replace(self.truist, budget_controller="Private person", budget_authority_evidence=authority)])
        self.assertIsNone(result["recommendation"]["budget_controller"])
        self.assertNotIn("private authority evidence", result["evidence"])

    def test_rejected_unreviewed_stale_and_future_records_are_excluded(self):
        for row in [replace(self.truist, rejected=True), replace(self.truist, approved=False),
                    replace(self.truist, evidence=replace(self.source, observed_on=date(2026, 1, 1))),
                    replace(self.truist, evidence=replace(self.source, observed_on=date(2027, 1, 1)))]:
            self.assertIsNone(self.answer([row])["recommendation"])

    def test_blocked_application_does_not_become_submission(self):
        self.assertIsNone(self.answer([replace(self.truist, action_kind="SUBMISSION")])["recommendation"])

    def test_amount_missing_or_invalid_is_unknown(self):
        for amount in [None, Decimal("-1"), Decimal("NaN")]:
            result = self.answer([replace(self.truist, proposed_amount=amount)])
            self.assertIsNone(result["recommendation"]["request"]["amount"])

    def test_priority_is_reviewed_not_largest_ask(self):
        other = replace(self.truist, organization="Synthetic prospect", proposed_amount=Decimal("10000000"), reviewed_priority=2)
        self.assertEqual(self.answer([other, self.truist])["recommendation"]["approach"], self.truist.organization)
