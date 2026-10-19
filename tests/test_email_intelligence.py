import json
import tempfile
import unittest
from pathlib import Path

from app.email_intelligence import build_funding_dashboard


class EmailIntelligenceTests(unittest.TestCase):
    def test_qts_deposit_is_executive_confirmed_not_bank_reconciled(self):
        result = build_funding_dashboard()
        self.assertEqual(result["verified_awarded_usd"], 15000)
        self.assertEqual(result["verified_received_usd"], 15000)
        self.assertEqual(result["confirmed_deposited_usd"], 15000)
        self.assertEqual(result["remaining_to_goal_awarded_usd"], 9985000)
        self.assertIsNone(result["bank_reconciled_usd"])
        qts = next(r for r in result["opportunities"] if r["id"] == "qts-2026")
        self.assertEqual(qts["deposit_evidence_kind"], "EXECUTIVE_CONFIRMATION")
        self.assertFalse(qts["bank_reconciled_verified"])

    def test_attestation_cannot_be_promoted_to_bank_reconciliation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            path.write_text(json.dumps({"as_of": "2026-10-13", "goal_usd": 10000000,
                "records": [{"stage": "awarded", "awarded_usd": 15000,
                "bank_reconciled_usd": 15000, "bank_reconciled_verified": True,
                "bank_reconciliation_evidence_kind": "EXECUTIVE_CONFIRMATION",
                "bank_reconciliation_evidence": "executive confirmation"}]}))
            self.assertIsNone(build_funding_dashboard(path)["bank_reconciled_usd"])

    def test_verified_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            path.write_text(json.dumps({
                "as_of": "2026-10-13", "goal_usd": 10000000,
                "records": [
                    {"stage": "awarded", "awarded_usd": 15000, "received_usd": None, "received_verified": False},
                    {"stage": "pre_application", "proposed_usd": 100000, "awarded_usd": 0},
                ],
            }))
            result = build_funding_dashboard(path)
            self.assertEqual(result["verified_awarded_usd"], 15000)
            self.assertEqual(result["verified_received_usd"], 0)
            self.assertEqual(result["remaining_to_goal_awarded_usd"], 9985000)


if __name__ == "__main__":
    unittest.main()
