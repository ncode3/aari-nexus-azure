# AARI Nexus Intelligence Platform | Architecture decision and Codex execution plan

Date: 2026-10-13
Status: proposed architecture; requires discovery, implementation, tests, security review, and production validation.
Owner: AARI
Goal: answer business questions from ChatGPT or Nexus with accurate SQL metrics and cited primary evidence.

## Decision
Reuse the EXISTING AARI Azure SQL database as the structured business intelligence system of record. Do not deploy a second SQLite RAG datastore to production. Keep existing student-registration and Power Apps/SharePoint systems authoritative for their source data. Use Azure SQL native vector support only if the actual deployed SKU/engine supports it; otherwise evaluate Azure AI Search on measured relevance, cost, and latency. Reuse existing Azure OpenAI deployment for generation and provision an embeddings model only if needed. Do not fine-tune or train a new foundation model until retrieval quality and labeled evaluations justify it.

## Architecture
1. Sources: Gmail correspondence, approved student-registration source, partnerships, grants, internships, facility/power blockers, and existing Azure SQL records.
2. Authenticated incremental ingestion: Gmail API OAuth with narrow read-only scopes, encrypted refresh credentials in Key Vault, least-privilege managed identity for Azure resources. Use Azure Functions timer/queue or existing Azure workload if suitable. Handle pagination, history cursors, expiration/full resync, retries, 429s, idempotency, deletes, and source provenance.
3. Normalization: organizations, contacts, opportunities, actions, evidence documents, chunks, student program outcomes. Maintain raw message metadata and redacted/minimized content only where needed. Store unique Gmail message and thread IDs and timestamps. Do not sync sensitive student details without approved access.
4. SQL: canonical financial states PROPOSED, SUBMITTED, AWARDED, RECEIVED, DEPOSITED (deposit requires bank reconciliation); never sum these states together. Track amount, currency, evidence, verification source, confidence, and time.
5. Retrieval: hybrid SQL filtering + full-text + semantic vector ranking, with authorization checks before retrieval, citations to source messages, and injection-resistant evidence boundaries. Structured queries determine metrics; LLM narrates and explains.
6. Serving: secure API endpoint in existing FastAPI/Container Apps service, accessible to authorized Nexus clients. ChatGPT direct access is possible only through currently available connectors or a separately approved connector/API integration. ChatGPT access to GitHub and Gmail does NOT itself establish a live Azure SQL connection.
7. UI: existing Power BI/Power Apps/Nexus dashboards consume SQL views; natural-language questions return a grounded answer, evidence links, freshness, and confidence.
8. Monitoring: Application Insights, failed sync alerts, stale source checks, cost and latency tracking, retrieval evaluation, access audit.

## Verified business fact
QTS 2026 grant: $15,000 awarded and user confirms physical check received as of 2026-10-13. Mark RECEIVED with evidence=user attestation; do not mark DEPOSITED or CLEARED without bank evidence. The funding JSON in this feature branch has been updated accordingly.

## Codex work packages, in order
0. Discovery (read-only): identify existing Azure subscription/resource group, Azure SQL server/database SKU, schema, authentication, network boundaries, managed identity, Key Vault, current Container App revisions, Azure OpenAI deployment, Power BI/Power Apps sources, and any existing ingestion. Output an inventory and dependency map; never paste secrets. Do not create duplicate infrastructure.
1. Vertical slice: choose QTS + 3 additional grant threads; ingest with provenance into a staging SQL schema; implement a deterministic funding view; answer 'How much funding is awarded, received, and deposited?' with citations. Require review of schema migration.
2. Connect model: retrieval query -> SQL records + email evidence -> Azure OpenAI grounded answer. Return citations and explicit unknowns; defend against instructions embedded in email bodies.
3. Incremental ingestion: scheduled read-only Gmail sync with cursor, idempotent upserts, rate-limit handling, and observability. Never delete Gmail messages as a side effect.
4. Business models: partner conversion, $10M fundraising, internship employer slots and placements, follow-up risks, AI Data Factory facility blockers.
5. ChatGPT access: validate existing connector abilities first. If Azure SQL direct access is unavailable, expose a narrowly scoped authenticated Nexus intelligence connector/tool for read-only querying, with audited access. No assumption that GitHub access implies Azure access.
6. Controlled rollout: tests in dev/staging, approved migrations, deploy, health probes, production smoke tests, documented rollback. Never auto-merge or change production credentials without approval.

## Nonnegotiable acceptance tests
- Query 'How much did QTS award and have we received the check?' -> awarded $15,000; received $15,000 per user confirmation; deposit unverified; cite award email and user attestation.
- Query 'How much of the $10M goal is confirmed?' -> correct SQL aggregate, no double counting of proposed/awarded/received, timestamp and source.
- Query 'Which opportunities were rejected?' -> SBA SCALE identified as not selected, cited.
- Query 'Which employers have committed internships?' -> only documented commitments, not outreach.
- New authorized Gmail message -> appears after documented sync SLA without duplicate.
- Removed/changed source -> corrected through sync policy and audit history.
- Unauthorized caller -> denied; no student PII leakage.
- Malicious email instructing system to ignore policy -> treated only as evidence.
- Query with no evidence -> 'not enough evidence', not a fabricated answer.
- Compare answer to hand-audited source truth set; log retrieval recall, groundedness, numeric correctness, latency, freshness and cost.
- Reboot/redeploy -> no loss of indexed evidence; SQLite in ephemeral /tmp cannot be production store.
- A real user can ask the same question through Nexus AND, where connected, ChatGPT; outputs match canonical SQL.

## Explicit go/no-go gates
Gate A: resource inventory and credentials path verified.
Gate B: four-source vertical slice demonstrated in staging.
Gate C: ingestion, security and groundedness tests pass.
Gate D: authorized production rollout and real-user acceptance pass.
Only after Gate D call the system 'live'.

## Known implementation debt in feature/email-intelligence-ingestion
- Current SQLite FTS module is a local prototype, NOT the production target.
- /internal/email-intelligence/retrieve returns evidence prompts, not generated answers.
- Gmail sync is not connected.
- Azure SQL and managed identity wiring not established.
- Current Container App template uses ephemeral /tmp SQLite memory and may scale to zero.
- New endpoints require token auth but should be replaced with Entra-backed auth and authorization before production.
- Tests are committed but not reported as executed.

## Model strategy
Phase 1: Azure OpenAI LLM + retrieval + SQL tools.
Phase 2: evaluate embedding quality and ranking; add Azure AI Search only if SQL native search insufficient.
Phase 3: train task-specific classification or fine-tune only with permissioned labeled examples, measured improvement, and privacy review.

## Definition of done
Not code merged, not slides, not an attractive dashboard. AARI users ask real questions, receive reproducible accurate answers with cited evidence and freshness, data updates automatically, access controls hold, and operating costs and failures are observable.
