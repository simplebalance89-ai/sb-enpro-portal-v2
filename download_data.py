#!/usr/bin/env python3
"""Download latest data files from Azure Blob storage."""

import os
import io
from pathlib import Path

# Try connection string first, then SAS
CONN_STR = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
SAS = os.environ.get("AZURE_BLOB_SAS", "")
CONTAINER = "fm-data"

FILES = [
    "Filtration_GPT_Filters_V25.csv",
    "Chemical_Compatibility_Crosswalk.xlsx", 
    "manufacturer_mapping.json"
]

def download_with_connection_string(filename):
    """Download using Azure SDK with connection string."""
    try:
        from azure.storage.blob import BlobServiceClient
        
        blob_service = BlobServiceClient.from_connection_string(CONN_STR)
        blob_client = blob_service.get_blob_client(container=CONTAINER, blob=filename)
        data = blob_client.download_blob().readall()
        
        local_path = Path("data") / filename
        local_path.write_bytes(data)
        size_mb = len(data) / (1024 * 1024)
        print(f"  Saved {filename} ({size_mb:.2f} MB)")
        return True
    except Exception as e:
        print(f"  Connection string failed: {e}")
        return False

def main():
    """Download all data files."""
    Path("data").mkdir(exist_ok=True)
    
    print("=" * 50)
    print("EnPro Data Downloader")
    print("=" * 50)
    
    if not CONN_STR and not SAS:
        print("No credentials set! Need AZURE_STORAGE_CONNECTION_STRING or AZURE_BLOB_SAS")
        return
    
    success = 0
    for filename in FILES:
        print(f"Downloading {filename}...")
        if CONN_STR:
            if download_with_connection_string(filename):
                success += 1
        else:
            print("  No connection string, skipping")
    
    print(f"Downloaded {success}/{len(FILES)} files")

if __name__ == "__main__":
    main()
