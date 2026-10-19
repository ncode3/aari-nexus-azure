// Separate opt-in proposal, never referenced by existing-sql.bicep or current Pulumi.
// Deployment would create a private endpoint and DNS zone group and incur cost.
targetScope = 'resourceGroup'

param location string
param sqlServerResourceId string
param privateEndpointSubnetResourceId string
param privateDnsZoneResourceId string
param privateEndpointName string
// This only creates a request; the SQL/network owner must review/approve it.
param connectionRequestMessage string

resource sqlEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: privateEndpointName
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    manualPrivateLinkServiceConnections: [
      {
        name: '${privateEndpointName}-sql'
        properties: {
          privateLinkServiceId: sqlServerResourceId
          groupIds: [ 'sqlServer' ]
          requestMessage: connectionRequestMessage
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: sqlEndpoint
  name: 'sql-private-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'sql'
        properties: {
          privateDnsZoneId: privateDnsZoneResourceId
        }
      }
    ]
  }
}

output privateEndpointResourceId string = sqlEndpoint.id
// Existing DNS zone/VNet link and Container Apps routing must be reviewed separately.
// No public firewall, allow-Azure-services rule, SQL SKU change, VNet, DNS zone,
// managed identity, OpenAI account, or SQL database is created here.
