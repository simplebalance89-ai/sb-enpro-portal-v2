// ═══════════════════════════════════════════════════════════════════════════════
// Azure Container Apps - API Hosting
// Replaces: Render/Docker hosting
// ═══════════════════════════════════════════════════════════════════════════════

param location string = resourceGroup().location
param appName string = 'enpro-mastermind'
param containerImage string
param searchEndpoint string
param searchKey string
param cosmosEndpoint string
param cosmosKey string

// Container Apps Environment
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${appName}-env'
  location: location
  properties: {
    zoneRedundant: false
  }
}

// Container App (API)
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      secrets: [
        {
          name: 'search-key'
          value: searchKey
        }
        {
          name: 'cosmos-key'
          value: cosmosKey
        }
        {
          name: 'openai-key'
          value: '@Microsoft.KeyVault(SecretUri=https://enpro-kv.vault.azure.net/secrets/openai-key/)'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'enpro-api'
          image: containerImage
          resources: {
            cpu: '0.5'
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: searchEndpoint
            }
            {
              name: 'AZURE_SEARCH_KEY'
              secretRef: 'search-key'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'COSMOS_KEY'
              secretRef: 'cosmos-key'
            }
            {
              name: 'USE_UNIFIED_HANDLER'
              value: 'true'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0  // Scale to zero when idle (cost savings)
        maxReplicas: 10
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
