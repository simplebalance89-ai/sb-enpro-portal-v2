#!/usr/bin/env python3
"""
Data Migration Script
Migrates product catalog from CSV to Azure AI Search
"""

import json
import pandas as pd
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
import os
import sys

# Configuration
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "https://enpro-search.search.windows.net")
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")

def get_embedding(text: str) -> list:
    """Generate embedding for semantic search."""
    client = AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        api_key=OPENAI_KEY,
        api_version="2024-12-01-preview"
    )
    
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return response.data[0].embedding

def migrate_products(csv_path: str = "export.csv"):
    """Migrate products from CSV to Azure AI Search."""
    
    print("📊 Loading product catalog...")
    df = pd.read_csv(csv_path)
    print(f"   Loaded {len(df)} products")
    
    # Search client
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name="enpro-products",
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    # Batch upload
    batch_size = 500
    documents = []
    
    for idx, row in df.iterrows():
        # Build rich description for embedding
        description = f"{row.get('Description', '')} {row.get('Final_Manufacturer', '')}"
        
        # Generate embedding (this takes time, ~19K products)
        try:
            embedding = get_embedding(description)
        except Exception as e:
            print(f"   ⚠️  Embedding failed for {row.get('Part_Number')}: {e}")
            embedding = []
        
        doc = {
            "Part_Number": str(row.get("Part_Number", "")),
            "Description": str(row.get("Description", "")),
            "Final_Manufacturer": str(row.get("Final_Manufacturer", "")),
            "Price": float(row.get("Price", 0)) if pd.notna(row.get("Price")) else 0.0,
            "Micron_Rating": float(row.get("Micron_Rating", 0)) if pd.notna(row.get("Micron_Rating")) else None,
            "Total_Stock": int(row.get("Total_Stock", 0)) if pd.notna(row.get("Total_Stock")) else 0,
            "Qty_Houston": int(row.get("Qty_Loc_10", 0)) + int(row.get("Qty_Loc_22", 0)) if pd.notna(row.get("Qty_Loc_10")) else 0,
            "Qty_Charlotte": int(row.get("Qty_Loc_12", 0)) if pd.notna(row.get("Qty_Loc_12")) else 0,
            "Alt_Codes": str(row.get("Alt_Code", "")).split(",") if pd.notna(row.get("Alt_Code")) else [],
            "Description_Vector": embedding
        }
        
        documents.append(doc)
        
        # Upload batch
        if len(documents) >= batch_size:
            search_client.upload_documents(documents=documents)
            print(f"   ✅ Uploaded {idx + 1}/{len(df)} products...")
            documents = []
    
    # Upload remaining
    if documents:
        search_client.upload_documents(documents=documents)
    
    print(f"\n🎉 Migration complete! {len(df)} products indexed.")

if __name__ == "__main__":
    if not SEARCH_KEY:
        print("❌ Error: AZURE_SEARCH_KEY environment variable required")
        sys.exit(1)
    
    migrate_products()
