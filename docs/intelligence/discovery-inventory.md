# Resource evidence handoff

Updated 2026-10-13 for PR #29, feature/email-intelligence-ingestion.

User instruction: accept the user's Azure Cloud Shell resource inventory as verified resource evidence and stop local Azure discovery. This review package follows that instruction. No additional Azure discovery was attempted while preparing it.

Evidence sources: the user's SQL deployment confirmation in this work order (2026-10-13), and the user's earlier Cloud Shell findings preserved in docs/intelligence/azure-sql-50-dollar-cost-gate.md at feature head 3709e8c92a6b02b9f85835a56f489b0a9c3ec5ee. These are accepted as resource evidence; they are not a verified application-to-SQL session or a completed security/cost gate. No additional local Azure discovery was attempted.

Existing SQL binding: resource group **rg-aari-intelligence-dev-eus-001**, server **sql-aari-intel-dev-eus-001**, database **sqldb-aari-nexus-intel-dev**, actual region **West US (westus)**. The eus naming suffix does not establish an East US location. User reports **Entra-only authentication**, **free SQL offer with overage disabled (AutoPause)**, and **no public SQL access**. Do not create another SQL server/database or change these controls.

Subscription/tenant IDs, SQL SKU/engine/schema, identity resource/client/principal IDs, selected source permissions, private endpoint/DNS path and total recurring price were not supplied in the deployment confirmation. No ARM IDs or missing permission grants are invented. The Bicep references use the confirmed names and explicitly selected subscription/identity parameters. confirmed-deployment.json preserves reported controls separately from verification flags.

| Evidence | Status |
| --- | --- |
| PR #29 engineering specification, head 3709e8c92a6b02b9f85835a56f489b0a9c3ec5ee | Verified through GitHub; original 21-file patch rebased without replacing the newer cost-gate commit |
| User SQL deployment | Existing SQL names, West US location, Entra-only, no public access, free offer/no overage accepted as user-confirmed resource evidence |
| User Cloud Shell managed identity | id-aari-nexus-dev-eus-001; AcrPull, Storage Blob Data Contributor and Key Vault Secrets User recorded; SQL data-plane grants not established |
| User Cloud Shell Container Apps | Revision 0000010 active; provisioning succeeded; HTTPS/external ingress; no IP restrictions; auth show {}; environment VNet configuration null, as recorded before this update |
| User Cloud Shell Azure OpenAI | gpt-4.1-mini deployment recorded; exact deployment resource ID/version/quota not supplied |
| SQL identity/SKU/schema | Names bound; subscription, SKU, engine features, schema and contained-user grants remain unknown |
| SharePoint/Power Apps/Jotform | Existing Cohort Desk integration documented; no new source reads, pipeline delivery or consent verification |
| Application-to-SQL connectivity | Not tested; inventory does not prove it |
| Effective SQL/Entra/Graph permissions | Not tested; resource existence does not prove access |
| Network security, private routing and DNS | Not tested; require independent review |
| Existing cost / incremental price | $50/month intelligence workload ceiling; free SQL offer does not cap private networking, DNS, logging or model costs; complete estimate remains unverified |
| Live Gmail/SharePoint delivery and ChatGPT SQL bridge | Not demonstrated |

The earlier temporary discovery report remains a historical record of that session's access limits. It is superseded as the workflow: repairing this local Azure environment is not a prerequisite for preparing or reviewing the patch. See review-package.md for the specific review gates.

Topology gate: the recorded Container Apps environment without VNet cannot be assumed to reach private SQL. Review an existing approved private path or a costed network change; never open SQL publicly to bypass the blocker. Entra-only SQL login also does not establish Entra API authorization for human callers. No application deployment, schema migration, additional network resource or public access is authorized by this task. See validate-existing-sql.md for the non-provisioning validation handoff.
