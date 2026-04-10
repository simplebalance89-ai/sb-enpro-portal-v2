// ═══════════════════════════════════════════════════════════════════════════════
// Azure AI Search - Product Catalog
// Replaces: pandas dataframe + fuzzy matching
// ═══════════════════════════════════════════════════════════════════════════════

param location string = resourceGroup().location
param searchName string = 'enpro-search'

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: location
  sku: {
    name: 'basic'  // Start here, scale to 'standard' when >10K queries/day
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    
    // Enable semantic search for natural language queries
    semanticSearch: 'free'
    
    // Vector search for semantic similarity
    vectorSearch: {
      profiles: [
        {
          name: 'enpro-vector-profile'
          algorithm: 'hnsw'
        }
      ]
    }
  }
}

// Search index definition
resource searchIndex 'Microsoft.Search/searchServices/indexes@2024-06-01-preview' = {
  parent: searchService
  name: 'enpro-products'
  properties: {
    fields: [
      {
        name: 'Part_Number'
        type: 'Edm.String'
        key: true
        searchable: true
        filterable: true
      }
      {
        name: 'Description'
        type: 'Edm.String'
        searchable: true
        analyzer: 'en.microsoft'
      }
      {
        name: 'Final_Manufacturer'
        type: 'Edm.String'
        searchable: true
        filterable: true
        facetable: true
      }
      {
        name: 'Price'
        type: 'Edm.Double'
        filterable: true
        sortable: true
      }
      {
        name: 'Micron_Rating'
        type: 'Edm.Double'
        filterable: true
        sortable: true
      }
      {
        name: 'Total_Stock'
        type: 'Edm.Int32'
        filterable: true
        sortable: true
      }
      {
        name: 'Qty_Houston'
        type: 'Edm.Int32'
        filterable: true
      }
      {
        name: 'Qty_Charlotte'
        type: 'Edm.Int32'
        filterable: true
      }
      {
        name: 'Alt_Codes'
        type: 'Collection(Edm.String)'
        searchable: true
      }
      {
        name: 'Description_Vector'
        type: 'Collection(Edm.Single)'
        hidden: true
        vectorSearchDimensions: 1536
        vectorSearchProfileName: 'enpro-vector-profile'
      }
    ]
    
    vectorSearch: {
      profiles: [
        {
          name: 'enpro-vector-profile'
          algorithmConfigurationName: 'hnsw-config'
        }
      ]
      algorithms: [
        {
          name: 'hnsw-config'
          kind: 'hnsw'
          parameters: {
            m: 4
            efConstruction: 400
            efSearch: 500
            metric: 'cosine'
          }
        }
      ]
    }
    
    semanticSearch: {
      configurations: [
        {
          name: 'enpro-semantic'
          prioritizedFields: {
            titleField: {
              fieldName: 'Part_Number'
            }
            contentFields: [
              {
                fieldName: 'Description'
              }
            ]
            keywordsFields: [
              {
                fieldName: 'Final_Manufacturer'
              }
            ]
          }
        }
      ]
    }
  }
}

output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchKey string = searchService.listAdminKeys().primaryKey
