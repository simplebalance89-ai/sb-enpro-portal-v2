"""
Voice Echo — Branch table for probable follow-ups.

This is NOT AI. It's a finite set of probable follow-up queries per intent.
When the user asks a first question, we fire these branches in parallel
against the pandas DataFrame (deterministic, no LLM) and cache the results.
Turn 2 hits the cache in milliseconds.

Pattern ported from Peter's v2.13 Voice Echo — a principle he proved works.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Branch:
    """One probable follow-up query."""
    key: str                          # Short identifier for the branch
    trigger_phrases: list[str]        # Phrases that match this branch in user input
    fetcher: Callable[..., Any]       # Function to run (takes context dict, returns results)
    description: str = ""             # Human-readable description


# ---------------------------------------------------------------------------
# INTENT: Pregame / customer / industry meeting
# ---------------------------------------------------------------------------
# When the user says something like "brewery customer meeting" or
# "pharmaceutical customer tomorrow", the first turn fetches the top in-stock
# parts for that Application. These are the probable follow-ups:

PREGAME_BRANCHES = [
    Branch(
        key="pregame.part_numbers",
        trigger_phrases=[
            "part number", "part numbers", "specific parts", "part #",
            "what parts", "which parts", "show me the parts",
        ],
        fetcher=lambda ctx: ctx.get("candidates", []),
        description="List specific part numbers from the candidate set",
    ),
    Branch(
        key="pregame.in_stock",
        trigger_phrases=[
            "in stock", "available", "what's available", "whats available",
            "any available", "stocked",
        ],
        fetcher=lambda ctx: [p for p in ctx.get("candidates", []) if int(p.get("Total_Stock", 0) or 0) > 0],
        description="Filter to only in-stock candidates",
    ),
    Branch(
        key="pregame.prices",
        trigger_phrases=[
            "price", "prices", "pricing", "cost", "how much",
            "what do they cost", "prices on those",
        ],
        fetcher=lambda ctx: [
            {"Part_Number": p.get("Part_Number"), "Price": p.get("Price"), "Last_Sell_Price": p.get("Last_Sell_Price")}
            for p in ctx.get("candidates", [])
        ],
        description="Return just PN + price for candidates",
    ),
    Branch(
        key="pregame.compare_top_two",
        trigger_phrases=[
            "compare", "compare those", "compare the top", "compare the first",
            "side by side", "difference between",
        ],
        fetcher=lambda ctx: ctx.get("candidates", [])[:2],
        description="Return top 2 candidates for comparison",
    ),
    Branch(
        key="pregame.houston_stock",
        trigger_phrases=[
            "houston", "in houston", "houston stock", "houston warehouse",
        ],
        fetcher=lambda ctx: [
            p for p in ctx.get("candidates", [])
            if (p.get("Stock", {}) or {}).get("Houston General Stock")
               or (p.get("Stock", {}) or {}).get("Houston Reserve")
        ],
        description="Candidates with Houston inventory",
    ),
    Branch(
        key="pregame.alternatives",
        trigger_phrases=[
            "alternative", "alternatives", "other options", "other manufacturers",
            "different brand", "substitute",
        ],
        fetcher=lambda ctx: ctx.get("alternatives", []),
        description="Same Product_Type from other manufacturers",
    ),
    Branch(
        key="pregame.questions_to_ask",
        trigger_phrases=[
            "questions", "what should i ask", "what to ask", "questions to ask",
            "what do i ask",
        ],
        fetcher=lambda ctx: ctx.get("questions", []),
        description="Pre-computed pregame questions for this industry",
    ),
    Branch(
        key="pregame.chemical_check",
        trigger_phrases=[
            "chemical", "compatibility", "compatible", "material",
        ],
        fetcher=lambda ctx: ctx.get("chemical_notes", []),
        description="Industry-typical chemical compatibility notes",
    ),
]


# ---------------------------------------------------------------------------
# INTENT: Part lookup
# ---------------------------------------------------------------------------
# When the user types a part number, we fetch the full record. These are the
# probable follow-ups:

LOOKUP_BRANCHES = [
    Branch(
        key="lookup.in_stock",
        trigger_phrases=["in stock", "available", "stock", "any stock"],
        fetcher=lambda ctx: ctx.get("product", {}).get("Stock", {}),
        description="Stock status for the looked-up part",
    ),
    Branch(
        key="lookup.price",
        trigger_phrases=["price", "how much", "cost", "pricing"],
        fetcher=lambda ctx: {
            "Part_Number": ctx.get("product", {}).get("Part_Number"),
            "Price": ctx.get("product", {}).get("Price"),
            "Last_Sell_Price": ctx.get("product", {}).get("Last_Sell_Price"),
        },
        description="Price for the looked-up part",
    ),
    Branch(
        key="lookup.substitute",
        trigger_phrases=[
            "substitute", "alternative", "alternatives", "replacement",
            "find me a", "something similar", "like this one",
        ],
        fetcher=lambda ctx: ctx.get("substitutes", []),
        description="Substitutes: same type/spec, different part, in stock",
    ),
    Branch(
        key="lookup.specs",
        trigger_phrases=["specs", "specifications", "details", "full info"],
        fetcher=lambda ctx: ctx.get("product", {}),
        description="Full spec sheet for the part",
    ),
    Branch(
        key="lookup.same_manufacturer",
        trigger_phrases=[
            "more from", "other products from", "same manufacturer",
            "same supplier", "from that supplier", "from pall", "from filtrox",
        ],
        fetcher=lambda ctx: ctx.get("same_manufacturer", []),
        description="Other in-stock parts from the same manufacturer",
    ),
]


# ---------------------------------------------------------------------------
# INTENT: Manufacturer search
# ---------------------------------------------------------------------------

MANUFACTURER_BRANCHES = [
    Branch(
        key="mfr.in_stock_only",
        trigger_phrases=["in stock", "available", "stocked"],
        fetcher=lambda ctx: [p for p in ctx.get("candidates", []) if int(p.get("Total_Stock", 0) or 0) > 0],
        description="Filter manufacturer products to in-stock only",
    ),
    Branch(
        key="mfr.by_application",
        trigger_phrases=[
            "for brewery", "for food", "for pharma", "for hydraulic",
            "for water treatment", "for oil and gas", "for hvac",
            "for chemical", "for industrial", "for compressed air",
        ],
        fetcher=lambda ctx: ctx.get("candidates", []),  # Already filtered by app in context build
        description="Manufacturer products for a specific Application",
    ),
    Branch(
        key="mfr.price_range",
        trigger_phrases=["cheapest", "most expensive", "price range", "under $"],
        fetcher=lambda ctx: sorted(
            ctx.get("candidates", []),
            key=lambda p: float(p.get("Last_Sell_Price", 0) or 0),
        ),
        description="Manufacturer products sorted by price",
    ),
    Branch(
        key="mfr.compare_top_two",
        trigger_phrases=["compare", "side by side", "compare those"],
        fetcher=lambda ctx: ctx.get("candidates", [])[:2],
        description="Top 2 products from this manufacturer for comparison",
    ),
]


# ---------------------------------------------------------------------------
# Branch routing — pick the right branch table per intent
# ---------------------------------------------------------------------------

BRANCHES_BY_INTENT: dict[str, list[Branch]] = {
    "pregame": PREGAME_BRANCHES,
    "application": PREGAME_BRANCHES,  # Same branches — pregame and application share shape
    "lookup": LOOKUP_BRANCHES,
    "manufacturer": MANUFACTURER_BRANCHES,
}


def match_branch(intent: str, user_message: str) -> Optional[Branch]:
    """
    Given an intent and the user's Turn 2+ message, return the matching
    branch (by trigger phrase) or None.

    Deterministic. Case-insensitive. Substring match on trigger phrases.
    """
    branches = BRANCHES_BY_INTENT.get(intent, [])
    if not branches:
        return None
    msg_lower = user_message.lower().strip()
    # Score each branch by how many trigger phrases hit
    best = None
    best_score = 0
    for branch in branches:
        score = sum(1 for phrase in branch.trigger_phrases if phrase in msg_lower)
        if score > best_score:
            best_score = score
            best = branch
    return best if best_score > 0 else None
