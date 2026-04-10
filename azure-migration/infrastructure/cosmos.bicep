// ═══════════════════════════════════════════════════════════════════════════════
// Azure Cosmos DB - Session State & Conversations
// Replaces: SQLite conversation_memory.py + quote_state.py
// ═══════════════════════════════════════════════════════════════════════════════

param location string = resourceGroup().location
param cosmosName string = 'enpro-cosmos'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'enpro-sessions'
  properties: {
    resource: {
      id: 'enpro-sessions'
    }
  }
}

// Conversations container (replaces conversation_memory.py)
resource conversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: ['/session_id']
        kind: 'Hash'
      }
      defaultTtl: 604800  // 7 days TTL (auto-cleanup)
    }
  }
}

// Quotes container (replaces quote_state.py)
resource quotesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'quotes'
  properties: {
    resource: {
      id: 'quotes'
      partitionKey: {
        paths: ['/session_id']
        kind: 'Hash'
      }
    }
  }
}

// Customers container (replaces customer_intel.py)
resource customersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'customers'
  properties: {
    resource: {
      id: 'customers'
      partitionKey: {
        paths: ['/customer_id']
        kind: 'Hash'
      }
    }
  }
}

output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosKey string = cosmosAccount.listKeys().primaryMasterKey
