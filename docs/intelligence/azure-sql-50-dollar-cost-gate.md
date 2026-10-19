# Azure SQL development cost gate ($50/month)

Approved planning ceiling: $50/month, inclusive of new SQL, network, monitoring, and any additional recurring resources. No approval to exceed. No production changes authorized.

## Deployed SQL resource (user-confirmed 2026-10-13)
Reuse resource group `rg-aari-intelligence-dev-eus-001`, server `sql-aari-intel-dev-eus-001`, database `sqldb-aari-nexus-intel-dev` in **West US**. Entra-only authentication, free offer with overage disabled (AutoPause), and no public SQL access are reported by the user. Do not create another server/database or change these policies. Application connectivity and total cost are not yet verified.

Azure SQL Database **free offer** applies to the deployed workload. Microsoft documents 100,000 vCore-seconds, 32 GB data, and 32 GB backup per month for an eligible free database. Select **Auto-pause database until next month when free limit reached**; never select pay-for-overages without renewed approval. The free offer is for development/PoC and lacks an SLA. Check subscription eligibility and region restrictions in portal before provisioning.

## Networking blocker
Current Container Apps environment has no VNet configured; Container App ingress is external, and platform auth returned an empty object. Do not create an internet-open SQL server, broad Azure firewall exemption, or database credentials in app settings to circumvent this. Investigate secure reachability and actual private connectivity charges. A private endpoint by itself does not establish VNet reachability from the current Container Apps environment. If private networking and migration exceed the $50 ceiling, do not deploy or connect the application; revise the development network design until cost and architecture are approved. Reuse the already deployed SQL resource.

## Mandatory cost validation
Produce an Azure Pricing Calculator estimate for West US with explicit SQL compute, data storage, backup, private endpoint hourly + data processing, VNet/Container Apps environment changes, DNS, logs, and outbound networking if applicable. Report fixed monthly baseline and usage-dependent range. Azure Budget alerts are **not hard spending caps**. Set alerts at $25/$40/$50 for the dedicated intelligence resource group; stop or pause new workloads before overage. Confirm all costs within the requested scope; other preexisting AARI Azure resources are outside this $50 incremental budget.

## Verified live discovery
User's Cloud Shell confirms managed identity `id-aari-nexus-dev-eus-001` with AcrPull, Storage Blob Data Contributor, Key Vault Secrets User. Container Apps environment VNet configuration is null; app revision `0000010` active; provisioning succeeded; HTTPS enforced, external ingress enabled, no IP security restrictions; auth show returned `{}`. Azure OpenAI `gpt-4.1-mini` is deployed. The pre-provisioning inventory contained no Microsoft.Sql resource; this historical finding is superseded by the SQL deployment confirmation above. Model version, identity IDs and current connectivity remain unverified beyond the recorded inventory.

## Business deliverable
Implement ranked fundraising pipeline with contact, recommended ask, decision authority, BANT evidence, next action, decision timeline, source citations, and separate proposed/awarded/check received/bank deposited statuses. QTS $15,000 deposited per executive confirmation; independently reconciled status unknown. Initial proposed asks: Truist $100k, Southern Company $75k, Georgia Piedmont Tech $50k, Google 2027 $150k. These are recommendations, not commitments.

## Gate
No additional Azure resource creation, application deployment, public SQL access or SQL schema migration until a secure connection path and complete estimate at or below $50/month are verified. Test the end-to-end business question against real data before claiming production completion.

Sources: https://learn.microsoft.com/en-us/azure/azure-sql/database/free-offer and https://learn.microsoft.com/en-us/azure/azure-sql/database/serverless-tier-billing
