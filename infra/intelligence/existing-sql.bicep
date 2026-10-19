// Review artifact only. All resources are existing; no SQL server/database is created.
targetScope = 'subscription'

param sqlSubscriptionId string = subscription().subscriptionId
@allowed(['rg-aari-intelligence-dev-eus-001'])
param sqlResourceGroupName string = 'rg-aari-intelligence-dev-eus-001'
@allowed(['sql-aari-intel-dev-eus-001'])
param sqlServerName string = 'sql-aari-intel-dev-eus-001'
@allowed(['sqldb-aari-nexus-intel-dev'])
param sqlDatabaseName string = 'sqldb-aari-nexus-intel-dev'
param identitySubscriptionId string
param identityResourceGroupName string
param identityName string

resource sqlServer 'Microsoft.Sql/servers@2023-08-01' existing = {
  name: sqlServerName
  scope: resourceGroup(sqlSubscriptionId, sqlResourceGroupName)
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01' existing = {
  parent: sqlServer
  name: sqlDatabaseName
}

resource entraOnly 'Microsoft.Sql/servers/azureADOnlyAuthentications@2023-08-01' existing = {
  parent: sqlServer
  name: 'Default'
}

resource nexusIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
  scope: resourceGroup(identitySubscriptionId, identityResourceGroupName)
}

output sqlServerResourceId string = sqlServer.id
output sqlDatabaseResourceId string = sqlDatabase.id
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output identityResourceId string = nexusIdentity.id
output identityClientId string = nexusIdentity.properties.clientId
output identityPrincipalId string = nexusIdentity.properties.principalId
// No passwords, API keys, connection strings or access-policy changes.

// Observed outputs for approved ARM validation; these do not modify settings.
output observedSqlLocation string = sqlDatabase.location
output observedPublicNetworkAccess string = sqlServer.properties.publicNetworkAccess
output observedEntraOnly bool = entraOnly.properties.azureADOnlyAuthentication
output observedUseFreeLimit bool = sqlDatabase.properties.useFreeLimit
output observedFreeLimitExhaustionBehavior string = sqlDatabase.properties.freeLimitExhaustionBehavior
