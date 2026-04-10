"""
Enpro Filtration Mastermind — Azure AI Search Client
Replaces pandas-based search.py with Azure AI Search (BM25 + semantic ranking).
Falls back to pandas search if Azure Search is unavailable.
"""

import logging
import os
import re
from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType

logger = logging.getLogger("enpro.search_azure")

SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY", "")
SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX", "enpro-products")

# Stock location mapping (same as search.py)
STOCK_LOCATIONS = {
    "Qty_Loc_10": "Houston General Stock",
    "Qty_Loc_12": "Charlotte",
    "Qty_Loc_22": "Houston Reserve",
    "Qty_Loc_30": "Kansas City",
}

MAX_RESULTS = 5

_client: Optional[SearchClient] = None


def get_client() -> Optional[SearchClient]:
    """Get or create the Azure Search client. Returns None if not configured."""
    global _client
    if _client:
        return _client
    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        logger.warning("Azure AI Search not configured — falling back to pandas")
        return None
    _client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX,
        credential=AzureKeyCredential(SEARCH_KEY),
    )
    logger.info(f"Azure AI Search connected: {SEARCH_ENDPOINT}/{SEARCH_INDEX}")
    return _client


def search_products(
    query: str,
    in_stock_only: bool = True,
    max_results: int = MAX_RESULTS,
) -> dict:
    """
    Search products using Azure AI Search with semantic ranking.

    Returns same format as search.py: {results, total_found, query, search_type}
    """
    client = get_client()
    if not client:
        return {"results": [], "total_found": 0, "query": query, "search_type": "azure_unavailable"}

    if not query or not query.strip():
        return {"results": [], "total_found": 0, "query": query, "search_type": "empty"}

    # Build filter for in-stock
    filter_expr = "Total_Stock gt 0" if in_stock_only else None

    # Detect part number patterns (letters+digits, no spaces) and add wildcard
    search_text = query.strip()
    is_part_number = bool(re.match(r'^[A-Za-z0-9\-/_.]+$', search_text) and
                          any(c.isdigit() for c in search_text) and
                          any(c.isalpha() for c in search_text))
    if is_part_number:
        search_text = f"{search_text}*"

    try:
        results = client.search(
            search_text=search_text,
            query_type=QueryType.SIMPLE,
            search_fields=[
                "Part_Number", "Supplier_Code", "Alt_Code",
                "Description", "Extended_Description", "Product_Type",
                "Final_Manufacturer", "Media", "Application", "Industry",
            ],
            select=[
                "Part_Number", "Description", "Extended_Description",
                "Product_Type", "Micron", "Media", "Max_Temp_F", "Max_PSI",
                "Flow_Rate", "Efficiency", "Final_Manufacturer", "Last_Sold_Date",
                "Last_Sell_Price", "Price_1",
                "Qty_Loc_10", "Qty_Loc_12", "Qty_Loc_22", "Qty_Loc_30",
                "Total_Stock",
            ],
            filter=filter_expr,
            top=max_results,
        )

        formatted = []
        total = 0
        for result in results:
            total += 1
            formatted.append(_format_search_result(result))

        return {
            "results": formatted,
            "total_found": total,
            "has_more": total >= max_results,
            "query": query,
            "search_type": "azure_search",
        }

    except Exception as e:
        logger.error(f"Azure Search failed: {e}")
        return {"results": [], "total_found": 0, "query": query, "search_type": "azure_error"}


def lookup_part(part_number: str) -> Optional[dict]:
    """Direct part number lookup via Azure Search."""
    client = get_client()
    if not client or not part_number:
        return None

    try:
        results = client.search(
            search_text=f"{part_number}*",
            search_fields=["Part_Number", "Supplier_Code", "Alt_Code"],
            top=1,
        )
        for result in results:
            return _format_search_result(result)
        return None
    except Exception as e:
        logger.error(f"Azure Search lookup failed: {e}")
        return None


def _format_search_result(result: dict) -> dict:
    """Format an Azure Search result into the same format as search.py format_product()."""
    product = {}

    # Visible fields
    visible = [
        "Part_Number", "Description", "Extended_Description", "Product_Type",
        "Micron", "Media", "Max_Temp_F", "Max_PSI", "Flow_Rate", "Efficiency",
        "Final_Manufacturer", "Last_Sold_Date",
    ]
    for field in visible:
        val = result.get(field)
        if val is not None and val != "" and val != 0:
            product[field] = val

    # Price
    last_sell = _to_float(result.get("Last_Sell_Price", 0))
    price_1 = _to_float(result.get("Price_1", 0))
    product["Last_Sell_Price"] = last_sell
    product["Price_1"] = price_1
    if last_sell > 0:
        product["Price"] = f"${last_sell:,.2f}"
    elif price_1 > 0:
        product["Price"] = f"${price_1:,.2f}"
    else:
        product["Price"] = "Contact Enpro for pricing"

    # Stock by location
    stock = {}
    for qty_col, loc_name in STOCK_LOCATIONS.items():
        qty = _to_float(result.get(qty_col, 0))
        if qty > 0:
            stock[loc_name] = int(qty)
    product["Stock"] = stock if stock else {"status": "Out of stock"}
    product["Total_Stock"] = int(_to_float(result.get("Total_Stock", 0)))

    return product


def _to_float(val) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
