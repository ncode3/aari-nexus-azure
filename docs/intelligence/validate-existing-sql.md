# Existing SQL validation handoff

Bind to user-confirmed rg-aari-intelligence-dev-eus-001 / sql-aari-intel-dev-eus-001 / sqldb-aari-nexus-intel-dev in West US. No server/database creation. The existing template contains only existing resources and non-secret metadata outputs. Do not deploy the application, modify network controls, migrate the SQL schema or grant permissions while validating the binding.

CI compiles both Bicep artifacts with pinned/checksummed Bicep v0.48.1 and validates the compiled SQL template has no resource declarations and exactly the confirmed names. This is compilation/binding validation, not live ARM reference resolution or application connectivity. The private-link proposal remains separate, unreferenced and billable if ever authorized.

From the existing authorized Azure Cloud Shell, use GET-only metadata checks (not run in this restricted local session):

```bash
sql_rg=rg-aari-intelligence-dev-eus-001
sql_server=sql-aari-intel-dev-eus-001
sql_db=sqldb-aari-nexus-intel-dev
az sql server show --resource-group "$sql_rg" --name "$sql_server" --query '{id:id,location:location,publicNetworkAccess:publicNetworkAccess}' --output json
az sql db show --resource-group "$sql_rg" --server "$sql_server" --name "$sql_db" --query '{id:id,location:location,status:status,sku:sku,useFreeLimit:useFreeLimit,freeLimitExhaustionBehavior:freeLimitExhaustionBehavior}' --output json
sql_server_id=$(az sql server show --resource-group "$sql_rg" --name "$sql_server" --query id --output tsv)
az rest --method get --url "https://management.azure.com${sql_server_id}/azureADOnlyAuthentications/Default?api-version=2023-08-01" --query properties --output json
```

Record sanitized results with timestamp and subscription scope. Expected reported controls: westus, publicNetworkAccess=Disabled, azureADOnlyAuthentication=true, useFreeLimit=true, freeLimitExhaustionBehavior=AutoPause. If any differ, stop and review; do not silently change them or add firewall exceptions. Do not export administrator names, secrets, connection strings, email bodies or student records.

Review SQL subscription and existing identity subscription/tenant/client/principal IDs before generating parameters. Actual ARM validation needs an authorized Azure context; no ARM validation or metadata output resolution was performed here. Independently demonstrate an authorized SELECT from the intended private workload network, TLS certificate verification and the intended managed identity, then test unauthorized API callers before enabling serving. No VNet in the recorded Container Apps environment is a reachability blocker, not permission to open SQL publicly.

Verify the complete $50/month intelligence budget in West US: SQL free-offer enforcement plus private endpoint/routing/DNS, environment changes, storage/backup, monitoring and model usage. Budget alerts are not spend caps. User approval of the ceiling does not establish that the design fits it. Keep review-plan connectivity, pricing, identity_permissions and network_design pending until each has distinct evidence.
