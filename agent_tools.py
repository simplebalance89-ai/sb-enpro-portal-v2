"""
Enpro Filtration Mastermind — Agent Tool Implementations

Thin wrappers around existing search.py and governance.py functions,
formatted as JSON-serializable outputs for the Azure AI Agent.
"""

import json
import logging
from typing import Any, Optional

import pandas as pd

from search import search_products, lookup_part, find_similar_products, lookup_part_with_chemicals
from governance import run_pre_checks

logger = logging.getLogger("enpro.agent_tools")

# Hardcoded seal ratings (from router.py CHEMICAL_SYSTEM_PROMPT)
SEAL_RATINGS = {
    "Sulfuric Acid (concentrated 98%)": {
        "Viton": "C (marginal — verify concentration)",
        "EPDM": "C (marginal)",
        "Buna-N": "D (AVOID)",
        "Nylon": "D (WARN — Do NOT use)",
        "PTFE": "A",
        "PVDF": "A",
        "316SS": "D (AVOID at high concentration — use Hastelloy C)",
        "note": "Carbon steel is NOT recommended. For dilute H2SO4 (<30%), 316SS may be acceptable.",
    },
    "MEK (Methyl Ethyl Ketone)": {
        "Viton": "B",
        "EPDM": "D (AVOID — swells in ketones)",
        "Buna-N": "D (AVOID)",
        "PTFE": "A",
        "316SS": "A",
    },
    "Ethylene Glycol": {
        "Viton": "A",
        "EPDM": "A",
        "Buna-N": "B",
        "PTFE": "A",
        "PVDF": "A",
        "316SS": "A",
    },
}


def _safe_json(obj: Any) -> str:
    """JSON-serialize with fallback for non-serializable types."""
    return json.dumps(obj, default=str, indent=2)


def tool_search_catalog(
    df: pd.DataFrame,
    query: str = "",
    in_stock_only: bool = True,
    max_results: int = 5,
    application: Optional[str] = None,
    manufacturer: Optional[str] = None,
) -> str:
    """Search the product catalog. Returns JSON string.

    Prefer passing `application` and/or `manufacturer` for structured
    filtering — the DataFrame is indexed on these and returns cleaner
    results than keyword search. Use `query` only when you need to narrow
    further by free text (e.g. 'depth sheet').
    """
    result = search_products(
        df,
        query=query,
        in_stock_only=in_stock_only,
        max_results=max_results,
        application=application,
        manufacturer=manufacturer,
    )
    products = result.get("results", [])
    return _safe_json({
        "products": products,
        "total_found": result.get("total_found", len(products)),
        "query": query,
        "application": application,
        "manufacturer": manufacturer,
        "in_stock_only": in_stock_only,
        "search_type": result.get("search_type", ""),
    })


def tool_lookup_part(df: pd.DataFrame, part_number: str) -> str:
    """Look up a specific part number. Returns JSON string."""
    product = lookup_part(df, part_number)
    if product:
        return _safe_json({"found": True, "product": product})
    return _safe_json({"found": False, "part_number": part_number})


def tool_check_chemical(
    df: pd.DataFrame,
    chemicals_df: pd.DataFrame,
    chemical_name: str,
    part_number: Optional[str] = None,
) -> str:
    """Check chemical compatibility. Returns JSON string with ratings."""
    result = {}

    # Check hardcoded seal ratings first
    for chem_key, ratings in SEAL_RATINGS.items():
        if chemical_name.lower() in chem_key.lower():
            result["seal_ratings"] = ratings
            result["chemical"] = chem_key
            result["source"] = "hardcoded (NON-NEGOTIABLE)"
            break

    # If part number provided, check its materials against crosswalk
    if part_number:
        part_data = lookup_part_with_chemicals(df, chemicals_df, part_number, chemical_name)
        if part_data:
            result["part_number"] = part_number
            result["detected_materials"] = part_data.get("detected_materials", [])
            result["media"] = part_data.get("media", "")
            if part_data.get("crosswalk_matches"):
                result["crosswalk_data"] = part_data["crosswalk_matches"]

    # If no hardcoded match, search crosswalk for the chemical
    if "seal_ratings" not in result and not chemicals_df.empty:
        from router import _search_chemical_crosswalk
        crosswalk = _search_chemical_crosswalk(chemical_name, chemicals_df)
        if crosswalk:
            result["crosswalk_data"] = json.loads(crosswalk)
            result["source"] = "crosswalk (filter media only — for seal ratings, contact Enpro engineering)"

    if not result:
        result = {
            "chemical": chemical_name,
            "found": False,
            "message": "Chemical not in database. Requires engineering review. Contact Enpro. Request a Safety Data Sheet (SDS).",
        }

    return _safe_json(result)


def tool_get_stock(df: pd.DataFrame, part_number: str) -> str:
    """Get stock levels for a specific part. Returns JSON string."""
    product = lookup_part(df, part_number)
    if not product:
        return _safe_json({"found": False, "part_number": part_number})

    stock = {
        "part_number": part_number,
        "found": True,
        "total_stock": product.get("Total_Stock", 0),
        "houston_general": product.get("Qty_Loc_10", 0),
        "houston_reserve": product.get("Qty_Loc_22", 0),
        "charlotte": product.get("Qty_Loc_12", 0),
        "kansas_city": product.get("Qty_Loc_30", 0),
    }
    return _safe_json(stock)


def tool_compare_parts(df: pd.DataFrame, part_numbers: list) -> str:
    """Compare multiple parts side by side. Returns JSON string."""
    products = []
    for pn in part_numbers[:5]:  # Cap at 5
        product = lookup_part(df, pn.strip())
        if product:
            products.append(product)

    if not products:
        return _safe_json({"found": False, "message": "None of the specified part numbers were found."})

    return _safe_json({
        "found": True,
        "count": len(products),
        "products": products,
    })


def tool_check_safety(message: str) -> str:
    """Run governance/safety pre-checks. Returns JSON string."""
    result = run_pre_checks(message)
    if result and result.get("intercepted"):
        return _safe_json({
            "safe": False,
            "escalation_reason": result.get("check", ""),
            "response": result.get("response", ""),
            "trigger": result.get("trigger", ""),
        })
    if result and result.get("advisory"):
        return _safe_json({
            "safe": True,
            "advisory": result.get("advisory", ""),
        })
    return _safe_json({"safe": True})


# Tool definitions for Azure AI Agent (OpenAI function calling format)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search the Enpro product catalog. PREFER structured filters (application, manufacturer) over keyword queries — they return cleaner results. Use query only for free-text narrowing within a filtered set. Returns matching products with part numbers, specs, pricing, and stock levels. ALWAYS translate industry language to one of the 9 Application buckets BEFORE calling this: brewery/wine/spirits/dairy/beverage → 'Food & Beverage', refinery/oilfield → 'Oil & Gas', data center/HVAC operator → 'HVAC', hydraulic system/lube oil → 'Hydraulic', municipal water/RO → 'Water Treatment', sterile/biotech/pharma → 'Pharmaceutical', compressed air → 'Compressed Air', solvents/caustics/acids → 'Chemical Processing', general manufacturing → 'Industrial'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {
                        "type": "string",
                        "description": "Filter by Application bucket (STRONGLY PREFERRED over query). Must be one of: 'Industrial', 'Compressed Air', 'Hydraulic', 'Oil & Gas', 'Water Treatment', 'Pharmaceutical', 'HVAC', 'Chemical Processing', 'Food & Beverage'. Translate user's industry language to one of these exact strings.",
                        "enum": ["Industrial", "Compressed Air", "Hydraulic", "Oil & Gas", "Water Treatment", "Pharmaceutical", "HVAC", "Chemical Processing", "Food & Beverage"],
                    },
                    "manufacturer": {
                        "type": "string",
                        "description": "Filter by manufacturer name (e.g., 'Pall', 'Filtrox', 'Graver', 'Parker', 'Donaldson'). Use when the user specifically names a brand.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Free-text keyword to narrow within a filtered set (e.g., 'depth sheet', '10 micron', 'membrane'). OPTIONAL — only use when you already have application or manufacturer set and need to narrow further. Do NOT put industry names here (use application instead).",
                    },
                    "in_stock_only": {
                        "type": "boolean",
                        "description": "If true, only return products with stock > 0. Default true.",
                        "default": True,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum products to return. Default 5.",
                        "default": 5,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_part",
            "description": "Look up a specific part number, supplier code, or alt code. Returns full product details including specs, pricing, and stock by warehouse location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "The part number to look up. Examples: 'HC9600FKZ4Z', 'EPE-10-5', '2004355'",
                    },
                },
                "required": ["part_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_chemical",
            "description": "Check chemical compatibility with filter materials. Returns A/B/C/D ratings for Viton, EPDM, Buna-N, PTFE, PVDF, 316SS. Use for any chemical compatibility question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemical_name": {
                        "type": "string",
                        "description": "Chemical name to check. Examples: 'sulfuric acid', 'MEK', 'sodium hydroxide'",
                    },
                    "part_number": {
                        "type": "string",
                        "description": "Optional part number to check specific materials against the chemical.",
                    },
                },
                "required": ["chemical_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock",
            "description": "Get current stock levels for a specific part across all warehouse locations (Houston General, Houston Reserve, Charlotte, Kansas City).",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "Part number to check stock for.",
                    },
                },
                "required": ["part_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_parts",
            "description": "Compare multiple parts side by side. Returns specs, pricing, and stock for each part. Use when the user wants to compare specific products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of part numbers to compare. Max 5.",
                    },
                },
                "required": ["part_numbers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_safety",
            "description": "Check if a user's request involves dangerous conditions that require engineering review. Run this BEFORE recommending products when the message mentions temperature, pressure, chemicals, or hazardous conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The user's message to check for safety triggers.",
                    },
                },
                "required": ["message"],
            },
        },
    },
]
