"""Offline review preflight. No SDK, subprocess, authentication, or deployment.

Cloud Shell inventory is accepted as resource evidence, not connectivity/security proof.
Even a ready plan still requires separate deployment authorization.
"""
from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

RESOURCE = re.compile(
    r"/subscriptions/([0-9a-fA-F-]{36})/resourceGroups/([^/]+)/providers/([^/]+)/(.+)$",
    re.IGNORECASE,
)
EXPECTED = {
    "sql_server_id": ("Microsoft.Sql", r"servers/[^/]+"),
    "sql_database_id": ("Microsoft.Sql", r"servers/[^/]+/databases/[^/]+"),
    "managed_identity_id": ("Microsoft.ManagedIdentity", r"userAssignedIdentities/[^/]+"),
    "container_app_id": ("Microsoft.App", r"containerApps/[^/]+"),
}
REQUIRED_REVIEWS = ("connectivity", "pricing", "identity_permissions", "network_design", "schema_migration", "data_access")


def resource_parts(value: object, provider: str, path_pattern: str):
    if not isinstance(value, str):
        return None
    match = RESOURCE.fullmatch(value)
    if not match or match[3].casefold() != provider.casefold() or not re.fullmatch(path_pattern, match[4], re.IGNORECASE):
        return None
    import uuid
    try:
        uuid.UUID(match[1])
    except ValueError:
        return None
    return match


def review_blockers(plan: dict) -> list[str]:
    if not isinstance(plan, dict):
        return ["Plan must be a JSON object"]
    for key in ("inventory", "resources", "network", "pricing", "reviews"):
        if not isinstance(plan.get(key), dict):
            return [f"Plan section must be an object: {key}"]
    if any(not isinstance(value, dict) for value in plan["reviews"].values()):
        return ["Review records must be objects"]
    for section, keys in (("inventory", ("evidence_reference",)),
                          ("network", ("dns_and_routing_evidence",)),
                          ("pricing", ("estimate_reference",))):
        if any(not isinstance(plan[section].get(key, ""), str) for key in keys):
            return [f"Evidence references must be strings: {section}"]
    if any(not isinstance(review.get(key, ""), str) for review in plan["reviews"].values()
           for key in ("reviewer", "evidence_reference")):
        return ["Review identity/evidence must be strings"]
    blockers = []
    if not isinstance(plan.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", plan["source_commit"]):
        blockers.append("Source commit not recorded")
    if plan.get("source_branch") != "feature/email-intelligence-ingestion":
        blockers.append("Wrong target branch")
    inventory = plan.get("inventory", {})
    if inventory.get("state") != "provided_verified" or not inventory.get("evidence_reference", "").strip():
        blockers.append("User Cloud Shell resource inventory not attached")
    resources = plan.get("resources", {})
    for key, (provider, pattern) in EXPECTED.items():
        if resource_parts(resources.get(key), provider, pattern) is None:
            blockers.append(f"Missing or malformed resource ID: {key}")
    server = resources.get("sql_server_id", "")
    database = resources.get("sql_database_id", "")
    if isinstance(server, str) and isinstance(database, str) and server and database and not database.casefold().startswith(server.casefold() + "/databases/"):
        blockers.append("Database is not a child of the reviewed server")
    for name in REQUIRED_REVIEWS:
        review = plan.get("reviews", {}).get(name, {})
        if (review.get("state") != "approved" or not review.get("reviewer", "").strip()
                or not review.get("evidence_reference", "").strip()):
            blockers.append(f"Review pending: {name}")
    network = plan.get("network", {})
    mode = network.get("mode")
    if mode not in {"existing_private", "new_private"}:
        blockers.append("Network design unresolved")
    if not network.get("dns_and_routing_evidence", "").strip():
        blockers.append("DNS and workload routing evidence missing")
    if mode == "new_private":
        for key, pattern in (("private_endpoint_subnet_id", r"virtualNetworks/[^/]+/subnets/[^/]+"),
                             ("private_dns_zone_id", r"privateDnsZones/privatelink\.database\.windows\.net")):
            if not resource_parts(network.get(key), "Microsoft.Network", pattern):
                blockers.append(f"Missing reviewed network resource: {key}")
        if not network.get("private_endpoint_name") or not network.get("location"):
            blockers.append("Private endpoint name/location missing")
    pricing = plan.get("pricing", {})
    if pricing.get("currency") != "USD" or pricing.get("sku_change_requested") is not False:
        blockers.append("Reuse-only SKU/currency decision missing")
    numbers = {}
    for key in ("baseline_monthly_usd", "estimated_monthly_delta_usd", "approved_monthly_delta_limit_usd"):
        try:
            if isinstance(pricing.get(key), bool):
                raise InvalidOperation
            value = Decimal(str(pricing.get(key)))
            if not value.is_finite() or value < 0:
                raise InvalidOperation
            numbers[key] = value
        except (InvalidOperation, ValueError):
            blockers.append(f"Price not reviewed: {key}")
    if (len(numbers) == 3 and numbers["estimated_monthly_delta_usd"] > numbers["approved_monthly_delta_limit_usd"]):
        blockers.append("Estimated cost exceeds reviewed limit")
    if not pricing.get("estimate_reference", "").strip():
        blockers.append("Price/usage estimate reference missing")
    if pricing.get("monthly_budget_ceiling_usd") != 50:
        blockers.append("Intelligence monthly budget ceiling must be $50")
    if len(numbers) == 3 and numbers["baseline_monthly_usd"] + numbers["estimated_monthly_delta_usd"] > 50:
        blockers.append("Total intelligence cost exceeds $50/month")
    return blockers


def existing_sql_parameters(plan: dict) -> dict:
    blockers = review_blockers(plan)
    if blockers:
        raise ValueError("Review not ready: " + "; ".join(blockers))
    resources = plan["resources"]
    server = resource_parts(resources["sql_server_id"], *EXPECTED["sql_server_id"])
    database = resource_parts(resources["sql_database_id"], *EXPECTED["sql_database_id"])
    identity = resource_parts(resources["managed_identity_id"], *EXPECTED["managed_identity_id"])
    values = {
        "sqlSubscriptionId": server[1], "sqlResourceGroupName": server[2],
        "sqlServerName": server[4].split("/")[1], "sqlDatabaseName": database[4].split("/")[3],
        "identitySubscriptionId": identity[1], "identityResourceGroupName": identity[2],
        "identityName": identity[4].split("/")[1],
    }
    return {"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
            "contentVersion": "1.0.0.0", "parameters": {key: {"value": value} for key, value in values.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--emit-parameters", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    blockers = review_blockers(plan)
    print(json.dumps({"review_ready": not blockers, "blockers": blockers,
                      "deployment_authorized": plan.get("deployment_authorized") is True,
                      "action": "offline validation only"}, indent=2))
    if args.emit_parameters:
        if blockers:
            return 2
        args.emit_parameters.write_text(json.dumps(existing_sql_parameters(plan), indent=2) + "\n", encoding="utf-8")
    return 2 if args.require_ready and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
