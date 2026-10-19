import copy
import json
import unittest
from pathlib import Path
from scripts.validate_intelligence_plan import existing_sql_parameters, review_blockers

ROOT = Path(__file__).resolve().parents[1]


class PlanTests(unittest.TestCase):
    def approved(self):
        plan = json.loads((ROOT / "infra/intelligence/review-plan.example.json").read_text())
        arm = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/synthetic/providers/"
        plan["inventory"] = {"state": "provided_verified", "evidence_reference": "synthetic inventory"}
        plan["resources"] = {
            "sql_server_id": arm + "Microsoft.Sql/servers/existing",
            "sql_database_id": arm + "Microsoft.Sql/servers/existing/databases/existing-db",
            "managed_identity_id": arm + "Microsoft.ManagedIdentity/userAssignedIdentities/existing-id",
            "container_app_id": arm + "Microsoft.App/containerApps/existing-app",
        }
        plan["network"] = {"mode": "existing_private", "dns_and_routing_evidence": "synthetic workload probe"}
        plan["pricing"] = {"currency": "USD", "baseline_monthly_usd": 10, "estimated_monthly_delta_usd": 2,
                           "approved_monthly_delta_limit_usd": 3, "sku_change_requested": False, "estimate_reference": "synthetic estimate", "monthly_budget_ceiling_usd": 50}
        for review in plan["reviews"].values():
            review.update(state="approved", reviewer="synthetic reviewer", evidence_reference="synthetic test")
        return plan

    def test_inventory_does_not_approve_connectivity_or_security(self):
        plan = self.approved()
        for review in plan["reviews"].values():
            review["state"] = "pending"
        self.assertIn("Review pending: connectivity", review_blockers(plan))
        self.assertIn("Review pending: identity_permissions", review_blockers(plan))
        with self.assertRaises(ValueError):
            existing_sql_parameters(plan)

    def test_ready_review_does_not_authorize_deployment(self):
        plan = self.approved()
        self.assertEqual(review_blockers(plan), [])
        self.assertFalse(plan["deployment_authorized"])
        self.assertEqual(existing_sql_parameters(plan)["parameters"]["sqlDatabaseName"]["value"], "existing-db")

    def test_each_required_review_blocks_generation(self):
        for name in self.approved()["reviews"]:
            plan = self.approved()
            plan["reviews"][name]["state"] = "pending"
            with self.subTest(name=name), self.assertRaises(ValueError):
                existing_sql_parameters(plan)

    def test_wrong_server_and_duplicate_infrastructure_are_rejected(self):
        plan = self.approved()
        plan["resources"]["sql_database_id"] = plan["resources"]["sql_database_id"].replace("servers/existing/", "servers/other/")
        self.assertIn("Database is not a child of the reviewed server", review_blockers(plan))
        plan = self.approved()
        plan["pricing"]["sku_change_requested"] = True
        self.assertTrue(review_blockers(plan))

    def test_cost_limit_and_invalid_prices_block(self):
        for amount in [4, -1, "NaN", None, True]:
            plan = self.approved()
            plan["pricing"]["estimated_monthly_delta_usd"] = amount
            self.assertTrue(review_blockers(plan))

    def test_new_private_endpoint_requires_reviewed_subnet_dns(self):
        plan = self.approved()
        plan["network"]["mode"] = "new_private"
        self.assertTrue(review_blockers(plan))

    def test_total_budget_includes_existing_intelligence_baseline(self):
        plan = self.approved()
        plan["pricing"].update(baseline_monthly_usd=49, estimated_monthly_delta_usd=2)
        self.assertIn("Total intelligence cost exceeds $50/month", review_blockers(plan))

    def test_public_sql_path_and_higher_budget_cannot_be_approved(self):
        plan = self.approved()
        plan["network"]["mode"] = "existing_restricted_public"
        self.assertIn("Network design unresolved", review_blockers(plan))
        plan = self.approved()
        plan["pricing"]["monthly_budget_ceiling_usd"] = 100
        self.assertTrue(review_blockers(plan))
