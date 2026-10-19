# PR #29 fundraising intelligence review package

Prepared 2026-10-13 against `3709e8c92a6b02b9f85835a56f489b0a9c3ec5ee` on `feature/email-intelligence-ingestion`. Prepared application of the original 21-file patch plus deployment/acceptance corrections. Nothing deployed, provisioned, migrated, consented or granted by this task. No live SQL/model/mailbox calls. Keep this work on the existing feature branch; do not merge the draft PR.

## First business acceptance

Ask: **Who should AARI approach next, how much should we request, who controls the budget, and what evidence supports the recommendation?**

Current review proposal from the PR seed/specification:

- Approach Truist Trusteed Foundations through Kristina Christy for a discovery conversation before applying.
- Discuss the **proposed $100,000 USD equipment ask**; it is not an award or an approved spending/application commitment.
- **Budget controller unknown.** The source identifies Kristina as a contact and requests a conversation; it does not establish that she controls or approves the budget. Ask for the actual budget holder, approval chain, amount limits and decision process.
- Evidence reference: PR #29 curated record `truist-equipment-2026`, Gmail message ID `1a1305a1e5db5d63`. Neither a live mailbox lookup nor citation-link verification occurred in this execution.
- Resolve one-year operating-history eligibility and provide the board-member list before recommending submission.
- Making this the highest-priority next conversation is an explicit proposal for human review, not a source fact or a claim that all prospects have been evaluated.

The first offline business test runs this contract before financial-total tests. It checks recipient, contact, proposed amount/currency, budget-authority unknown, blockers and citation. Negative cases cover rejected/unreviewed/stale/cross-scope evidence and contacts mislabeled as controllers. The prepared SQL regression starts with the same four-part assertion using synthetic identities. A full production recommendation acceptance still requires authorized SQL rows, fresh primary-source evidence, actual citation access and evidence-backed budget authority or a clearly actionable unknown. Do not label the offline fixture a live recommendation service.

## Review artifacts

| Artifact | Purpose / limitations |
| --- | --- |
| infra/intelligence/existing-sql.bicep | Existing server/database/identity references and non-secret outputs only. No SQL creation, SKU change, credential or role changes |
| infra/intelligence/private-link-proposal.bicep | Separate optional private endpoint + existing private DNS zone group proposal. Not imported into current deployment. Requires cost/network approval; uses a manual connection request |
| infra/intelligence/review-plan.example.json | Resource inventory and distinct connectivity/pricing/identity/network/schema/data review records. Blank values are intentional |
| scripts/validate_intelligence_plan.py | Offline preflight and parameter generation only; no deploy capability. A reviewed plan does not itself authorize deployment |
| sql/intelligence/001_fundraising_schema.sql | One-time additive isolated schema on existing staging SQL. No seed data, database creation, user creation, vectors/full-text provisioning or runtime migration hook |
| sql/intelligence/002_reader_permissions.review.sql | Disabled-by-default, separately bound source-scope/read-view grant proposal to an already reviewed SQL contained user |
| sql/intelligence/003_staging_regression.review.sql | Synthetic approach/ask/authority/evidence, snapshot/retraction/deposit and SQL principal isolation tests inside a rollback transaction. Not executed |
| app/fundraising_recommendations.py | Deterministic contract over trusted already-authorized rows; not wired to a live API/SQL adapter |
| app/intelligence_policy.py and route/bot changes | Deny empty/unlisted chat access; prototype HTTP routes allowed only in explicitly opted-in local/test environments |

## Fundraising model

Tenant/source scope bounds every business entity, with composite foreign keys preventing cross-scope relationships. Organizations, contacts, opportunities, budget-authority claims, evidence, minimized chunks, financial snapshots, action items and incremental ingestion checkpoints remain distinct. No student-registration records are introduced; SharePoint remains authoritative.

Financial events are cumulative snapshots per opportunity and financial state, with unique revisions. Views use the latest approved revision, never add revisions or count awarded+received+deposited as separate money. Latest retraction produces unknown instead of resurrecting an older amount. Missing/expired/retracted evidence produces NULL/unknown; totals expose unknown counts. Currencies are grouped separately. DEPOSITED accepts EXECUTIVE_CONFIRMATION or BANK_RECONCILIATION evidence with attribution retained; RECONCILED requires BANK_RECONCILIATION. QTS deposited=$15,000 per executive confirmation; independent bank reconciliation remains unknown. RECEIVED can be supported by an approved attestation. Actual partial-payment/reversal/accounting policy still needs finance review.

Next-approach view requires approved action/ask/contact evidence, distinguishes budget control from influence, blocks applications with unresolved eligibility/blockers, and exposes authority unknown when no verified controller is available. Query with reviewed priority + due date ordering; do not rank solely by largest request. Runtime must enforce freshness, per-caller/source ACL and citations before model narration. No unrestricted model-generated SQL is provided.

SQL RLS denies access unless USER_NAME() has an administrator-managed tenant/source grant. The read role gets five explicit views and no raw table or DDL/write permissions. No runtime principal receives membership in the schema migration. Shared managed identity RLS is a database-principal boundary, **not individual human authorization**; Entra caller/source ACLs remain a required independent layer. There is no SESSION_CONTEXT header/parameter trust shortcut. A future ingestion principal gets only approved idempotent write procedures, not broad schema/table DML.

## Security remediation and remaining gates

Prepared code changes:

1. Every Telegram command now requires an explicitly allowed chat, and the Pulumi plan requires a nonempty approved chat allowlist. Existing group-chat membership risks still require review; prefer approved private chats or separate user-level checks for sensitive operations.
2. Shared-token SQLite/seed intelligence endpoints return 503 in dev/staging/production, even if a token/opt-in flag is supplied. Only APP_ENV=local/test with NEXUS_LOCAL_EMAIL_PROTOTYPE=true may use the local prototype, still requiring a token. No Container Apps template sets the opt-in flag. This is containment, not an implementation of production Entra authentication.
3. SQLite connections now explicitly close after commit/rollback, resolving a Windows cleanup failure. SQLite remains local prototype storage; no production SQLite system is introduced.
4. Source metadata is separated from excerpts; restricted sources cannot be marked index_allowed=true and the retrieval view only returns approved unexpired internal indexed excerpts. Reviewer/data minimization and prompt-injection controls still need real integration tests.

Required independent review records:

| Gate / owner | Evidence needed before provisioning/migration/deployment |
| --- | --- |
| Resource binding / Azure owner | User Cloud Shell inventory, timestamp/scope and exact ARM IDs. Accept it as verified inventory, not session/network/security proof |
| Connectivity / application + SQL owners | Existing authorized workload-to-database query, server/database identity, managed identity selection, driver/token audience, TLS Encrypt=yes/TrustServerCertificate=no and negative error handling. No broad firewall opening |
| Pricing / finance + Azure owner | Baseline actual usage and SQL SKU; incremental compute/storage/query load, private endpoint hourly/data/DNS charges if needed, logs/retention, model/embedding usage; numeric monthly limit and dated regional estimate. Reuse is not necessarily $0 |
| Identity permissions / SQL + Entra owners | Verify tenant/client/principal IDs, SQL contained-user identity and narrow grants, existing memberships; no db_owner, generic datareader/writer, or ARM Contributor assumption. Review source ACLs and any server Graph directory-resolution permissions separately |
| Network design / network owner | Reuse current private path if functional. If new private endpoint necessary: subnet approval, address capacity, DNS zone/VNet links, routing from Container Apps, SQL public-network policy, connection approval and rollback. DNS zone group alone does not establish DNS reachability. Never add 0.0.0.0/allow-Azure-services firewall rule |
| Schema migration / SQL + finance owners | Name/collision check, snapshot semantics, index/scale implications, permissions, retention, restore/rollback plan and staging regression results |
| Data/source access / business owners | Gmail app/read-only consent/refresh storage, source review/retention, selected SharePoint access, budgets and primary-source/citation validity |
| Release / authorized owner | Explicit staging then production deployment authorization, immutable image, smoke tests and rollback; independent of review_ready flag |

Production API work remains pending: validate Entra token signature/issuer/tenant/audience/expiry using trusted metadata and pinned algorithms, authorize roles and source scopes before retrieval, separate reader/ingestor permissions, bound request/rate limits and model spend, redact logs, record query audit IDs, and alert on failed/stale ingestion. Do not trust x-ms/client-identity headers without a validated platform boundary. Preserve existing network controls while preparing their reviewed replacement; this patch changes no cloud configuration.

## Pricing and infrastructure choices

SQL region is user-confirmed West US, with the free SQL offer and overage disabled. No numeric cost or SKU is invented. The complete intelligence workload must fit the $50/month ceiling, including SQL baseline and incremental private networking/logs/model costs; the free SQL offer is not a cap on those services. The example plan requires a baseline, incremental estimate, approved limit, estimate reference and pricing reviewer. It rejects requested SQL SKU changes because this package is reuse-only. New SQL/database/model/Search infrastructure would require a separate necessity decision and reviewed proposal. Existing-SQL Bicep references do not declare additional capacity. The optional private-link proposal is a billable resource change and is not connected to the application's Pulumi entrypoint.

Use review-plan fields only after reading the supplied resource inventory. Each approval must carry reviewer and separate evidence; copying an inventory reference into connectivity/security approvals is not valid evidence. The validator records administrative readiness, not a cryptographic proof of reviewer identity or live cloud state.

## Validation and limits

Run dependency-free checks:

```powershell
python scripts/run_intelligence_offline_tests.py
python -m compileall -q app infra scripts tests
python scripts/validate_intelligence_plan.py infra/intelligence/review-plan.example.json --require-ready
```

The last command is intentionally nonzero for the unbound/unreviewed example. In this execution, offline tests and Python compilation are exercised; SQL scripts remain unexecuted. Both Bicep files subsequently compiled successfully in PR CI on implementation commit 83c666a4c4a95ca93d96eb32bf6e0e9b99e305ff. HTTP integration tests in tests/test_email_api_security.py require FastAPI/httpx; installation was blocked by local network socket restrictions. Subsequent [PR CI](https://github.com/ncode3/aari-nexus-azure/actions/runs/39321784730) passed all 80 unit/HTTP tests and compiled-template binding checks. SQL/cloud acceptance remains unrun; unit tests and compilation do not establish live connectivity or permissions.

On an approved build workstation, run Bicep build/lint for both templates before any deployment review. On approved staging, run the SQL migration and synthetic regression with sqlcmd -b after reviewers sign off; check cross-tenant/source isolation, all permission denials, expired/deleted evidence, native feature support and concurrency/idempotency. Confirm Entra and actual source/citation tests before a production endpoint exists. Full repository regressions also remain required.

Rollback: no cloud rollback is needed for this preparation. Once separately authorized, rollback app by restoring prior immutable image while keeping prototype endpoints disabled. Revoke only the reviewed role/scope grants if needed. An additive SQL schema remains until a reviewed retention/archive plan; do not automatically drop it or restore over unrelated existing data. Reverse a newly approved private endpoint/DNS change only after checking other workload dependencies.

## Primary references

- [SQL existing resource API](https://learn.microsoft.com/en-us/azure/templates/microsoft.sql/2023-08-01/servers/databases)
- [Microsoft SQL RLS](https://learn.microsoft.com/en-us/sql/relational-databases/security/row-level-security)
- [Entra principals and Azure SQL](https://learn.microsoft.com/en-us/azure/azure-sql/database/authentication-aad-service-principal?view=azuresql)

These describe service capabilities; none proves AARI's live configuration or grants.
