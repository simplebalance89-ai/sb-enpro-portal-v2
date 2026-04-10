"""
Index products from Azure Blob Storage CSV into Azure AI Search.
Run once to populate the index, then again whenever product data changes.

Usage:
    python scripts/index_products.py
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)
from azure.storage.blob import BlobServiceClient

# ----- Config -----
SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "https://enpro-ai-search.search.windows.net")
SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY", "")
SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX", "enpro-products")

STORAGE_CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
BLOB_CONTAINER = os.environ.get("AZURE_BLOB_CONTAINER", "fm-data")
STATIC_CSV = "static_crosswalk.csv"
INVENTORY_CSV = "inventory_live.csv"


def create_index(index_client: SearchIndexClient):
    """Create or update the search index schema."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="Part_Number", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SearchableField(name="Supplier_Code", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="Alt_Code", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="Description", type=SearchFieldDataType.String),
        SearchableField(name="Extended_Description", type=SearchFieldDataType.String),
        SearchableField(name="Product_Type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="Final_Manufacturer", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="Media", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="Efficiency", type=SearchFieldDataType.String),
        SearchableField(name="Application", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="Industry", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="Micron", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="Max_Temp_F", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="Max_PSI", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="Flow_Rate", type=SearchFieldDataType.String),
        SimpleField(name="Last_Sold_Date", type=SearchFieldDataType.String),
        SimpleField(name="Last_Sell_Price", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="Price_1", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="Qty_Loc_10", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="Qty_Loc_12", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="Qty_Loc_22", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="Qty_Loc_30", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="Total_Stock", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
    ]

    index = SearchIndex(name=SEARCH_INDEX, fields=fields)
    index_client.create_or_update_index(index)
    print(f"Index '{SEARCH_INDEX}' created/updated with {len(fields)} fields")


def load_csv_from_blob(filename: str) -> pd.DataFrame:
    """Load CSV from Azure Blob Storage."""
    if not STORAGE_CONN:
        print(f"No AZURE_STORAGE_CONNECTION_STRING — trying local file: data/{filename}")
        return pd.read_csv(f"data/{filename}", dtype=str).fillna("")

    blob_service = BlobServiceClient.from_connection_string(STORAGE_CONN)
    blob_client = blob_service.get_blob_client(container=BLOB_CONTAINER, blob=filename)
    data = blob_client.download_blob().readall()
    return pd.read_csv(io.BytesIO(data), dtype=str).fillna("")


def safe_float(val) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def safe_int(val) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def index_products():
    """Load CSVs, merge, and upload to Azure AI Search."""
    # Load data
    print("Loading static crosswalk...")
    static_df = load_csv_from_blob(STATIC_CSV)
    print(f"  Loaded {len(static_df)} static products")

    print("Loading live inventory...")
    try:
        inv_df = load_csv_from_blob(INVENTORY_CSV)
        print(f"  Loaded {len(inv_df)} inventory records")
        # Rename columns to match static_crosswalk (same logic as data_loader.py)
        inv_rename = {}
        if "P21_Item_ID" in inv_df.columns and "Part_Number" not in inv_df.columns:
            inv_rename["P21_Item_ID"] = "Part_Number"
        if "Qty_Loc10" in inv_df.columns:
            inv_rename["Qty_Loc10"] = "Qty_Loc_10"
            inv_rename["Qty_Loc12"] = "Qty_Loc_12"
            inv_rename["Qty_Loc22"] = "Qty_Loc_22"
            inv_rename["Qty_Loc30"] = "Qty_Loc_30"
        if inv_rename:
            inv_df = inv_df.rename(columns=inv_rename)
            print(f"  Renamed inventory columns: {inv_rename}")
        # Merge on Part_Number
        df = static_df.merge(inv_df, on="Part_Number", how="left", suffixes=("", "_inv"))
    except Exception as e:
        print(f"  Inventory load failed ({e}), using static only")
        df = static_df

    # Normalize column names
    rename_map = {}
    for col in df.columns:
        if col.endswith("_Final"):
            base = col.replace("_Final", "")
            if base not in df.columns:
                rename_map[col] = base
    if rename_map:
        df = df.rename(columns=rename_map)

    # Calculate Total_Stock
    stock_cols = ["Qty_Loc_10", "Qty_Loc_12", "Qty_Loc_22", "Qty_Loc_30"]
    for col in stock_cols:
        if col not in df.columns:
            df[col] = "0"

    df["Total_Stock"] = sum(pd.to_numeric(df[col], errors="coerce").fillna(0) for col in stock_cols)

    # Fill NaN to prevent JSON encoding errors
    df = df.fillna("")

    # Prepare documents for indexing
    print(f"Preparing {len(df)} documents for indexing...")
    documents = []
    for idx, row in df.iterrows():
        doc = {
            "id": str(idx),
            "Part_Number": str(row.get("Part_Number", "")),
            "Supplier_Code": str(row.get("Supplier_Code", "")),
            "Alt_Code": str(row.get("Alt_Code", "")),
            "Description": str(row.get("Description", "")),
            "Extended_Description": str(row.get("Extended_Description", "")),
            "Product_Type": str(row.get("Product_Type", "")),
            "Final_Manufacturer": str(row.get("Final_Manufacturer", row.get("Manufacturer", ""))),
            "Media": str(row.get("Media", "")),
            "Efficiency": str(row.get("Efficiency", "")),
            "Application": str(row.get("Application", "")),
            "Industry": str(row.get("Industry", "")),
            "Micron": str(row.get("Micron", "")),
            "Max_Temp_F": str(row.get("Max_Temp_F", "")),
            "Max_PSI": str(row.get("Max_PSI", "")),
            "Flow_Rate": str(row.get("Flow_Rate", "")),
            "Last_Sold_Date": str(row.get("Last_Sold_Date", "")),
            "Last_Sell_Price": safe_float(row.get("Last_Sell_Price", 0)),
            "Price_1": safe_float(row.get("Price_1", 0)),
            "Qty_Loc_10": safe_int(row.get("Qty_Loc_10", 0)),
            "Qty_Loc_12": safe_int(row.get("Qty_Loc_12", 0)),
            "Qty_Loc_22": safe_int(row.get("Qty_Loc_22", 0)),
            "Qty_Loc_30": safe_int(row.get("Qty_Loc_30", 0)),
            "Total_Stock": safe_int(row.get("Total_Stock", 0)),
        }
        documents.append(doc)

    # Upload in batches of 1000
    credential = AzureKeyCredential(SEARCH_KEY)
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX,
        credential=credential,
    )

    batch_size = 1000
    total_uploaded = 0
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        result = search_client.upload_documents(documents=batch)
        succeeded = sum(1 for r in result if r.succeeded)
        total_uploaded += succeeded
        print(f"  Batch {i // batch_size + 1}: {succeeded}/{len(batch)} succeeded")

    print(f"\nDone! Indexed {total_uploaded}/{len(documents)} products into '{SEARCH_INDEX}'")


if __name__ == "__main__":
    # Create index
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY),
    )
    create_index(index_client)

    # Index products
    index_products()
