# AARI Enterprise AI Operating Layer

**Status:** Target architecture and staged implementation plan, not a claim of production readiness.  
**Owner:** Atlanta AI & Robotics Initiative (AARI)  
**Implementation tracker:** [Issue #26](https://github.com/ncode3/aari-nexus-azure/issues/26)

## Executive position

AARI Nexus is the **AARI-owned enterprise AI operating layer**: the policy, orchestration, memory, integration, and observability fabric that can route work to local or cloud models. AARI should control this layer, its source code, its data contracts, and its operational governance rather than couple workflows to any one AI vendor.

Ownership of code and workflows does not imply ownership of third-party models, cloud infrastructure, licensed services, or unrestricted rights to data. Verify applicable licenses and contractual rights before commercializing.

## Architectural principle

**Own orchestration; choose inference.** Preserve the existing Azure Nexus runtime and Power Apps/SharePoint Cohort Desk. Add Odysseus as a user-facing client and local Ollama/Qwen as an optional inference provider, alongside Azure OpenAI. The policy boundary remains in Nexus, not inside an untrusted model.

```text
Authorized user
   |
Odysseus / approved client
   | authenticated request
AARI Nexus (Azure FastAPI)
   |-- identity, authorization, Arbiter, approval gates, audit
   |-- workflow orchestration / action packages
   |-- existing SQLite operational memory (MVP)
   |-- Cohort Desk read-only retrieval -> Microsoft Graph -> SharePoint
   |      ^ Power Apps is the staff interface to the same records
   |
   +-- model routing
          |-- Azure OpenAI (existing)
          +-- secure, opt-in local Ollama/Qwen adapter (planned)
```

## Verified repository baseline (October 2026)

- FastAPI, Azure Container Apps, Azure OpenAI, Telegram bot, Key Vault, Blob artifacts, telemetry, and Arbiter exist in the repository.
- Existing operational memory is SQLite. Do **not** describe it as a validated production vector RAG index.
- Cohort Desk uses SharePoint as source of truth; Power Apps is the staff editing interface. Nexus has read-only aggregate reporting code, but live access requires Graph permissions, configuration, and deployment validation.
- The Azure V1 README explicitly excludes Ollama/local model routing. Odysseus-to-Nexus integration has **not** been demonstrated.
- Current bot workflow drafts action packages; external execution is intentionally not implemented. Do not advertise autonomous cross-system actions as production functionality.
- Deployment state, current Azure resource health, production permissions, and end-to-end connectivity remain unverified.

## Operating model

1. Client submits an authenticated task with user identity and scope.
2. Nexus authorizes the task and tools; denies by default when authorization is missing.
3. Nexus retrieves only authorized, necessary data with provenance.
4. Model router selects local Qwen or Azure OpenAI based on policy, capability, privacy, availability, and cost.
5. Model produces a proposed response or structured action; the model never grants itself tool permissions.
6. Nexus validates output, records minimal redacted telemetry, and requests explicit approval for consequential writes, communications, commitments, or external actions.
7. Only approved, implemented tools execute, with audit and rollback where feasible.

## Security and privacy requirements

- Never expose Ollama to the public internet. Prefer an authenticated outbound-initiated channel from the local environment, TLS, least-privilege short-lived credentials, and explicit network allowlists.
- Keep the existing Arbiter but do not treat keyword-based prompt classification as a sufficient authorization system. Add independent identity, tool-level RBAC/ABAC, prompt-injection defenses, and execution isolation.
- SharePoint selected-site or selected-list read permissions; avoid tenant-wide grants.
- Do not route identifiable applicant data to local or cloud models until an approved data-flow review covers consent, retention, access, encryption, and provider processing terms.
- Preserve Cohort Desk's current aggregate-only behavior. Synthetic records first. No automated employment eligibility or hiring decisions.
- Never claim local inference makes the entire hybrid workflow offline; Nexus/Graph/cloud calls traverse networks.
- Keep secrets in approved secret stores; never commit tokens or candidate records.

## Initial enterprise use case

**Workforce pipeline intelligence:** “Hey Odysseus, ask Nexus for the current authorized cohort readiness and follow-up summary, identify aggregate bottlenecks, and prepare a cited management brief.”

Success requires correct SharePoint-derived totals, test-record exclusion, provenance, access denials, safe failure on unavailable data, no personal records in model prompts or logs, and no changes to applicant data.

Future phases, subject to separate approvals: individual candidate assistance, grant operations, partner CRM, email/calendar actions, infrastructure operations, and reusable tenant-isolated enterprise deployments.

## Delivery phases and gates

| Phase | Deliverable | Exit gate |
| --- | --- | --- |
| 0 | Audit repository, Azure deployment, Graph access, Power Apps link, data contracts | Verified evidence; no production changes |
| 1 | Provider-neutral model interface and secure local Qwen adapter | Unit/integration tests; no public model endpoint |
| 2 | Authenticated Odysseus-to-Nexus read-only workflow | Synthetic-data end-to-end test with denied-access cases |
| 3 | Approved aggregate Cohort Desk pilot | Reconciled metrics, provenance, privacy checks, latency/cost benchmark |
| 4 | Controlled action tools | Explicit human approval, least privilege, audit, rollback |
| 5 | Enterprise hardening/commercialization assessment | Threat model, SLOs, tenant isolation, licensing/IP and TCO review |

## Metrics

Track task completion and grounded-answer accuracy, authorization failures, hallucinated counts, p50/p95 latency, local GPU/energy use, cloud token and infrastructure costs, availability, audit completeness, and human interventions. Compare against the existing cloud-only workflow, including engineering and maintenance costs.

## Non-goals

Do not rebuild Cohort Desk, duplicate student databases, create a second RAG stack without an identified gap, alter the existing production Azure stack, expose local model ports, or claim autonomous execution before it is built and tested.

## Source references

- [Repository README](../README.md)
- [Cohort Desk integration](cohort-desk.md)
- [Architecture](architecture.md)
- [Implementation issue #26](https://github.com/ncode3/aari-nexus-azure/issues/26)
