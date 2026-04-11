"""
Pregame Pipeline — the Edge Crew pattern for filtration pregame.

Flow:
  Step 1 — Knowledge lookup (pandas, no LLM)
  Step 2 — Candidate fetch (pandas, no LLM)
  Step 3 — Parallel reasoning (8 narrow prompts, fired with delay offsets)
  Step 4 — Aggregate + grade
  Step 5 — Gatekeeper (governance.py rules)
  Step 6 — Return Turn 1 answer + cache other branches

Pattern: Peter's v2.13 Voice Echo + Edge Crew v3 crowdsource_grade.
Proven 18 for 18 on NBA picks. Same shape, different domain.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

import httpx
import pandas as pd

from pregame_prompts import TOOLS, build_user_message, render_branch
from context_store import set_context, get_context
from governance import run_pre_checks

logger = logging.getLogger("enpro.pregame_pipeline")


# ---------------------------------------------------------------------------
# STEP 1 — Knowledge lookup
# ---------------------------------------------------------------------------

_KB_CACHE: dict[str, Any] = {}


def _load_kb() -> dict[str, Any]:
    """Load kb/filtration_reference.json once at module init."""
    if _KB_CACHE:
        return _KB_CACHE
    kb_path = os.path.join(os.path.dirname(__file__), "kb", "filtration_reference.json")
    if not os.path.exists(kb_path):
        logger.warning(f"KB file not found: {kb_path}")
        return {}
    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            _KB_CACHE.update(json.load(f))
        logger.info(f"Loaded filtration_reference.json: {len(_KB_CACHE)} top-level keys")
    except Exception as e:
        logger.error(f"Failed to load KB: {e}")
    return _KB_CACHE


def step1_knowledge(application_bucket: str) -> dict[str, Any]:
    """
    Pull John's KB entry for this Application bucket.
    Returns a dict with title, typical_specs, recommended_products, etc.
    No LLM. Pure lookup.
    """
    kb = _load_kb()
    bucket_key = f"application:{application_bucket.lower().replace(' & ', '_').replace(' ', '_')}"
    # Common alias mappings
    aliases = {
        "application:food_&_beverage": "application:food_beverage",
        "application:oil_&_gas": "application:oil_gas",
    }
    bucket_key = aliases.get(bucket_key, bucket_key)
    return kb.get(bucket_key, {})


# ---------------------------------------------------------------------------
# STEP 2 — Candidate fetch (pandas, no LLM)
# ---------------------------------------------------------------------------

def step2_fetch_candidates(
    df: pd.DataFrame,
    application_bucket: str,
    max_results: int = 15,
) -> list[dict[str, Any]]:
    """
    Deterministic pandas query: parts in the given Application bucket,
    narrowed by John's expert rules (kb/application_filters.py) BEFORE any
    LLM fires, then sorted by stock + activity priority.

    Flow:
      1. Apply John's strict rules (preferred_manufacturers + media + micron_range)
      2. If strict returns zero → fall back to loose rules (micron only)
      3. If still zero → fall back to just Application + OK-FILTRATION
      4. Sort by activity + stock priority

    This narrows "200 F&B parts" down to "15 Filtrox cellulose depth sheets
    in 0.45-1.0 µm range" BEFORE Claude ever sees data.

    Returns list of formatted product dicts.
    """
    if df.empty:
        return []

    # Load John's expert rules for this bucket
    try:
        from kb.application_filters import get_filter_rules
        rules = get_filter_rules(application_bucket)
    except Exception as e:
        logger.warning(f"[step2] failed to load filter rules: {e}")
        rules = {}

    matches = df.copy()

    # Mandatory filter 1: Item_Category = OK-FILTRATION (89.6% of catalog)
    if "Item_Category" in matches.columns:
        matches = matches[matches["Item_Category"].astype(str).str.upper() == "OK-FILTRATION"]

    # Mandatory filter 2: Application bucket match
    if "Application" in matches.columns:
        app_norm = application_bucket.strip().lower()
        matches = matches[matches["Application"].astype(str).str.lower().str.strip() == app_norm]

    if matches.empty:
        logger.info(f"[step2] no parts for Application='{application_bucket}' + OK-FILTRATION")
        return []

    # Save the loose baseline in case the strict filter empties everything
    loose_baseline = matches.copy()
    pre_strict_count = len(matches)

    # --- STRICT FILTER: John's expert rules narrow the candidate set ---

    # Preferred manufacturers (Filtrox for brewery, Pall for pharma, etc.)
    # Check Manufacturer (clean, from Product_Group prefix) and Supplier (P21
    # source of truth). Final_Manufacturer is the polluted legacy field — DO
    # NOT reference it anywhere in new code, even as an alias fallback.
    if rules.get("preferred_manufacturers"):
        pref_mfrs = [m.strip().lower() for m in rules["preferred_manufacturers"]]
        mfr_cols = [c for c in ("Manufacturer", "Supplier") if c in matches.columns]
        if mfr_cols:
            mask = pd.Series(False, index=matches.index)
            for col in mfr_cols:
                col_lower = matches[col].astype(str).str.lower().str.strip()
                for mfr in pref_mfrs:
                    # Substring match: "Pall Corporation" → "pall",
                    # "FILTROX North America Inc." → "filtrox", etc.
                    mask = mask | col_lower.str.contains(mfr, na=False, regex=False)
            narrowed = matches[mask]
            if not narrowed.empty:
                matches = narrowed
                logger.info(f"[step2] manufacturer filter: {pre_strict_count} → {len(matches)}")

    # Preferred media types
    if rules.get("preferred_media") and "Media" in matches.columns:
        pref_media = [m.strip().lower() for m in rules["preferred_media"]]
        col_lower = matches["Media"].astype(str).str.lower().str.strip()
        mask = pd.Series(False, index=matches.index)
        for med in pref_media:
            mask = mask | col_lower.str.contains(med, na=False, regex=False)
        narrowed = matches[mask]
        if not narrowed.empty:
            matches = narrowed
            logger.info(f"[step2] media filter → {len(matches)}")

    # Micron range (strict spec window from John)
    if rules.get("micron_range") and "Micron" in matches.columns:
        lo, hi = rules["micron_range"]
        micron_numeric = pd.to_numeric(matches["Micron"], errors="coerce")
        narrowed = matches[(micron_numeric >= lo) & (micron_numeric <= hi)]
        if not narrowed.empty:
            matches = narrowed
            logger.info(f"[step2] micron range {lo}-{hi} → {len(matches)}")

    # --- FALLBACK: If strict narrowing emptied the set, try loose micron range ---
    if matches.empty and rules.get("fallback_micron_range") and "Micron" in loose_baseline.columns:
        lo, hi = rules["fallback_micron_range"]
        micron_numeric = pd.to_numeric(loose_baseline["Micron"], errors="coerce")
        matches = loose_baseline[(micron_numeric >= lo) & (micron_numeric <= hi)]
        logger.info(f"[step2] fallback to loose micron {lo}-{hi} → {len(matches)}")

    # --- FINAL FALLBACK: Just the baseline (Application + OK-FILTRATION) ---
    if matches.empty:
        matches = loose_baseline
        logger.info(f"[step2] final fallback to loose baseline → {len(matches)}")

    # Priority filter: prefer ACTIVE, prefer in-stock
    if "Activity_Flag" in matches.columns:
        # Active first, then others
        matches = matches.copy()
        matches["_is_active"] = (matches["Activity_Flag"].astype(str).str.upper() == "ACTIVE").astype(int)
    else:
        matches["_is_active"] = 0

    if "Total_Stock" in matches.columns:
        matches["_in_stock"] = (pd.to_numeric(matches["Total_Stock"], errors="coerce").fillna(0) > 0).astype(int)
        matches["_stock_qty"] = pd.to_numeric(matches["Total_Stock"], errors="coerce").fillna(0)
    else:
        matches["_in_stock"] = 0
        matches["_stock_qty"] = 0

    matches = matches.sort_values(
        by=["_is_active", "_in_stock", "_stock_qty"],
        ascending=[False, False, False],
    )

    # HARD FILTER: prefer ACTIVE + in-stock. Only fall back to dormant/OOS
    # if there are literally no active+stocked parts that match. This is
    # what makes Turn 1 answers actually useful instead of "here's a
    # dormant part from 5-10 years ago that's also out of stock."
    active_stocked = matches[(matches["_is_active"] == 1) & (matches["_in_stock"] == 1)]
    if len(active_stocked) >= 1:
        matches = active_stocked
        logger.info(f"[step2] hard filter to ACTIVE+stocked → {len(matches)}")
    else:
        # Try just active (any stock)
        active_any = matches[matches["_is_active"] == 1]
        if len(active_any) >= 1:
            matches = active_any
            logger.info(f"[step2] no active+stocked, falling back to ACTIVE any-stock → {len(matches)}")
        else:
            logger.info(f"[step2] no active parts at all, keeping dormant sorted by stock → {len(matches)}")

    matches = matches.drop(columns=["_is_active", "_in_stock", "_stock_qty"])

    # Format via search.format_product for clean output
    from search import format_product
    return [format_product(row) for _, row in matches.head(max_results).iterrows()]


# ---------------------------------------------------------------------------
# STEP 3 — Parallel reasoning (Anthropic API)
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-5"
DELAY_BETWEEN_CALLS_MS = 100  # Space out the parallel calls slightly

# Branch → model tier + context slice mapping.
# Different branches have different reasoning needs. top_picks is the one
# call that actually matters for Turn 1 quality (Claude Opus). Everything
# else uses Sonnet or Haiku — faster, cheaper, same quality for the job.
#
# context_slice options:
#   "full" — everything (candidates + KB + customer context)
#   "top_candidates" — only top 5 candidates + customer context
#   "candidates_customer" — all candidates + customer, no KB
#   "candidates_only" — just candidates, no KB or customer
#   "industry_only" — just the application bucket name + typical questions from KB
#   "app_only" — just the application bucket name
#   "customer_only" — just the customer context (for risk scan)
BRANCH_CONFIG: dict[str, dict] = {
    "top_picks":       {"model": "claude-opus-4-5",    "slice": "full",               "max_tokens": 2048},
    "compare_top_2":   {"model": "claude-sonnet-4-5",  "slice": "top_candidates",     "max_tokens": 1024},
    "pregame_summary": {"model": "claude-sonnet-4-5",  "slice": "candidates_customer","max_tokens": 1024},
    "questions_to_ask":{"model": "claude-haiku-4-5",   "slice": "industry_only",      "max_tokens": 512},
    "alternatives":    {"model": "claude-haiku-4-5",   "slice": "candidates_only",    "max_tokens": 1024},
    "risk_flags":      {"model": "claude-haiku-4-5",   "slice": "customer_only",      "max_tokens": 512},
    "cross_sell":      {"model": "claude-haiku-4-5",   "slice": "candidates_only",    "max_tokens": 512},
    "scenario_next":   {"model": "claude-haiku-4-5",   "slice": "app_only",           "max_tokens": 512},
}


def _slice_context(
    slice_name: str,
    customer_context: str,
    application: str,
    kb_json: str,
    candidates_json: str,
    candidates: list[dict],
) -> dict[str, str]:
    """
    Return only the context fields needed for this slice. Reduces tokens per call.
    """
    top5_json = json.dumps(candidates[:5], default=str, indent=2)
    top2_json = json.dumps(candidates[:2], default=str, indent=2)

    if slice_name == "full":
        return {
            "customer_context": customer_context,
            "application": application,
            "kb_context": kb_json,
            "candidates_json": candidates_json,
        }
    if slice_name == "top_candidates":
        return {
            "customer_context": customer_context,
            "application": application,
            "kb_context": "",
            "candidates_json": top5_json,
        }
    if slice_name == "candidates_customer":
        return {
            "customer_context": customer_context,
            "application": application,
            "kb_context": "",
            "candidates_json": candidates_json,
        }
    if slice_name == "candidates_only":
        return {
            "customer_context": "",
            "application": application,
            "kb_context": "",
            "candidates_json": candidates_json,
        }
    if slice_name == "industry_only":
        return {
            "customer_context": customer_context,
            "application": application,
            "kb_context": kb_json,
            "candidates_json": "[]",
        }
    if slice_name == "customer_only":
        return {
            "customer_context": customer_context,
            "application": application,
            "kb_context": "",
            "candidates_json": "[]",
        }
    if slice_name == "app_only":
        return {
            "customer_context": "",
            "application": application,
            "kb_context": "",
            "candidates_json": "[]",
        }
    # Default fallback — full context
    return {
        "customer_context": customer_context,
        "application": application,
        "kb_context": kb_json,
        "candidates_json": candidates_json,
    }


async def _call_claude(
    prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    timeout: int = 60,
    tool: Optional[dict] = None,
):
    """
    One Anthropic API call.

    If tool is None, returns the text content as a string (legacy path).
    If tool is provided, forces tool_choice to that tool and returns the parsed
    tool_input dict — the schema is enforced by the Anthropic API, not by
    parsing prose on our side. Returns empty string / empty dict on failure.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }
    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if tool:
        body["tools"] = [tool]
        body["tool_choice"] = {"type": "tool", "name": tool["name"]}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=body)
            if resp.status_code != 200:
                logger.warning(f"Claude API {resp.status_code}: {resp.text[:200]}")
                return {} if tool else ""
            data = resp.json()
            content = data.get("content", []) or []
            if tool:
                # Find the tool_use block matching our forced tool name
                for block in content:
                    if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
                        tool_input = block.get("input")
                        return tool_input if isinstance(tool_input, dict) else {}
                logger.warning(
                    f"Claude returned no tool_use block for {tool['name']}: "
                    f"stop_reason={data.get('stop_reason')}"
                )
                return {}
            for block in content:
                if block.get("type") == "text":
                    return block.get("text", "")
            return ""
    except Exception as e:
        logger.warning(f"Claude call failed: {e}")
        return {} if tool else ""


async def step3_parallel_reason(
    branch_keys: list[str],
    customer_context: str,
    application: str,
    kb_context: str,
    candidates: list[dict],
    api_key: str,
    model: str = DEFAULT_MODEL,  # fallback model if BRANCH_CONFIG misses
) -> dict[str, str]:
    """
    Fire N narrow reasoning prompts in parallel against Claude.

    Each branch uses its own tier (Opus / Sonnet / Haiku) and context slice
    from BRANCH_CONFIG. top_picks gets full context on Opus because it's the
    one call that makes or breaks Turn 1 quality. Everything else uses smaller
    models with narrower context.

    Expected Turn 1 cost: ~$0.03 (down from ~$0.16 on all-Opus).
    Expected Turn 1 time: ~5-7s (bounded by Opus, Haiku/Sonnet finish faster).

    Returns dict keyed by branch_key with the model's text response.
    """
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping parallel reasoning")
        return {}

    candidates_json = json.dumps(candidates[:10], default=str, indent=2)
    kb_json = json.dumps(kb_context, default=str, indent=2) if isinstance(kb_context, (dict, list)) else str(kb_context)

    async def _fire_branch(idx: int, key: str) -> tuple[str, str]:
        # Stagger the calls slightly to avoid burst rate limits
        await asyncio.sleep((idx * DELAY_BETWEEN_CALLS_MS) / 1000)

        # Look up this branch's model tier and context slice
        cfg = BRANCH_CONFIG.get(key, {})
        branch_model = cfg.get("model", model)
        slice_name = cfg.get("slice", "full")
        max_tokens = cfg.get("max_tokens", 2048)

        # Build narrow context for this branch's specific job
        ctx = _slice_context(
            slice_name=slice_name,
            customer_context=customer_context,
            application=application,
            kb_json=kb_json,
            candidates_json=candidates_json,
            candidates=candidates,
        )

        prompt = build_user_message(branch_key=key, **ctx)
        tool = TOOLS.get(key)
        if not prompt or not tool:
            return (key, "")

        # Force structured output via tool_choice. Schema in pregame_prompts.TOOLS
        # is enforced by the Anthropic API — no prose JSON parsing on our side.
        tool_input = await _call_claude(
            prompt,
            api_key=api_key,
            model=branch_model,
            max_tokens=max_tokens,
            tool=tool,
        )
        # Render the structured dict into a human-readable string so downstream
        # Turn 2 cache hits and Turn 1 display keep working unchanged.
        rendered = render_branch(key, tool_input) if isinstance(tool_input, dict) else ""
        keys_count = len(tool_input) if isinstance(tool_input, dict) else 0
        logger.info(
            f"  branch[{key}] via {branch_model} ({slice_name}) → "
            f"tool_input={keys_count} keys, rendered={len(rendered)} chars"
        )
        return (key, rendered)

    tasks = [_fire_branch(i, key) for i, key in enumerate(branch_keys)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, str] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Branch exception: {result}")
            continue
        key, text = result
        if text:
            output[key] = text
    return output


# ---------------------------------------------------------------------------
# STEP 4 — Aggregate (simple — just collect, no cross-model grading yet)
# ---------------------------------------------------------------------------

def step4_aggregate(reasoning_results: dict[str, str]) -> dict[str, Any]:
    """
    Collect the 8 parallel outputs. For now this is a straight pass-through.
    Future: add cross-branch grading when we introduce a second model to vote.
    """
    return {
        "branches_completed": list(reasoning_results.keys()),
        "branches_count": len(reasoning_results),
        "results": reasoning_results,
    }


# ---------------------------------------------------------------------------
# STEP 5 — Gatekeeper (rule check)
# ---------------------------------------------------------------------------

def step5_gatekeeper(customer_context: str, application: str) -> dict[str, Any]:
    """
    Run governance.py pre-checks against the customer context to catch
    escalation triggers (>400F, >150 PSI, H2S, etc.) before presenting.
    """
    check = run_pre_checks(customer_context) if customer_context else None
    if check and check.get("intercepted"):
        return {
            "safe": False,
            "escalation_reason": check.get("check", ""),
            "response": check.get("response", ""),
            "trigger": check.get("trigger", ""),
        }
    if check and check.get("advisory"):
        return {"safe": True, "advisory": check.get("advisory", "")}
    return {"safe": True}


# ---------------------------------------------------------------------------
# STEP 6 — Orchestrator: run the whole pipeline
# ---------------------------------------------------------------------------

async def run_pregame_pipeline(
    df: pd.DataFrame,
    session_id: str,
    user_message: str,
    application_bucket: str,
    customer_context: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """
    Full pregame pipeline. Returns the Turn 1 user-facing answer AND caches
    all 8 branch results in context_store keyed by session_id.

    Args:
        df: merged product DataFrame
        session_id: session key for context_store
        user_message: the user's Turn 1 message
        application_bucket: one of the 9 Application buckets
        customer_context: optional customer details if known
        api_key: Anthropic API key (reads env var if not set)
        model: Claude model name

    Returns:
        dict with:
          response: the Turn 1 answer text (for immediate return to user)
          products: the candidate set (for product card rendering)
          intent: "pregame"
          cost: estimate
          context_key: session_id for future retrieval
    """
    start_time = time.time()
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    model = model or os.environ.get("AZURE_AGENT_DEPLOYMENT", DEFAULT_MODEL)
    if not model.startswith("claude"):
        model = DEFAULT_MODEL

    logger.info(f"[pregame] session={session_id[:12]} app={application_bucket} msg={user_message[:60]}")

    # Step 1 — KB lookup
    kb = step1_knowledge(application_bucket)
    logger.info(f"[pregame] step1: kb keys={list(kb.keys())[:5]}")

    # Step 2 — Pandas fetch
    candidates = step2_fetch_candidates(df, application_bucket, max_results=15)
    logger.info(f"[pregame] step2: {len(candidates)} candidates")

    if not candidates:
        return {
            "response": (
                f"I don't have any active in-stock parts for {application_bucket} "
                "right now. Check with the office on alternatives."
            ),
            "products": [],
            "intent": "pregame",
            "cost": "$0",
            "context_key": session_id,
        }

    # Step 3 — Parallel reasoning (8 branches)
    all_branches = list(TOOLS.keys())
    reasoning = await step3_parallel_reason(
        branch_keys=all_branches,
        customer_context=customer_context or user_message,
        application=application_bucket,
        kb_context=kb,
        candidates=candidates,
        api_key=api_key,
        model=model,
    )
    logger.info(f"[pregame] step3: {len(reasoning)}/{len(all_branches)} branches completed")

    # Step 4 — Aggregate
    aggregated = step4_aggregate(reasoning)

    # Step 5 — Gatekeeper
    gate = step5_gatekeeper(customer_context or user_message, application_bucket)
    logger.info(f"[pregame] step5: safe={gate.get('safe')}")

    # Step 6 — Cache + return Turn 1 answer
    elapsed = time.time() - start_time
    context_obj = {
        "session_id": session_id,
        "timestamp": time.time(),
        "intent": "pregame",
        "application": application_bucket,
        "customer_context": customer_context or user_message,
        "knowledge": kb,
        "candidates": candidates,
        "reasoning": reasoning,
        "aggregated": aggregated,
        "gatekeeper": gate,
        "elapsed_seconds": elapsed,
    }
    set_context(session_id, context_obj)
    logger.info(f"[pregame] cached context for session {session_id[:12]} ({elapsed:.1f}s)")

    # Gatekeeper override: if not safe, return escalation immediately
    if not gate.get("safe"):
        return {
            "response": gate.get("response", "This application needs engineering review."),
            "products": [],
            "intent": "escalation",
            "cost": f"~${0.01 * len(reasoning):.2f}",
            "context_key": session_id,
        }

    # Primary Turn 1 answer comes from the pregame_summary branch
    turn1_answer = reasoning.get("pregame_summary", "").strip()
    if not turn1_answer:
        # Fallback: synthesize from top_picks if pregame_summary failed
        turn1_answer = reasoning.get("top_picks", "").strip() or (
            f"Found {len(candidates)} active {application_bucket} parts in stock. "
            f"Leading with {candidates[0].get('Part_Number', 'top pick')}. "
            "Ask me what you want to know."
        )

    return {
        "response": turn1_answer,
        "products": candidates[:5],
        "intent": "pregame",
        "cost": f"~${0.02 * len(reasoning):.2f}",
        "context_key": session_id,
        "structured": False,
    }


# ---------------------------------------------------------------------------
# Turn 2+ handler — cache hit = instant answer
# ---------------------------------------------------------------------------

# User phrase → branch key mapping for Turn 2+ cache lookups.
# Deterministic, case-insensitive substring match. Order matters — first match wins.
# Expanded 2026-04-11 to cover spec/price/stock/supplier follow-ups that
# previously fell through to the agent with no context.
TURN2_BRANCH_MAP = [
    # Comparison (keep first — "compare" is unambiguous)
    (["compare the top", "compare those", "compare the first", "side by side",
      "compare them", "compare it", "which is better", "pros and cons"], "compare_top_2"),

    # Top picks / recommendations
    (["top pick", "top 3", "best pick", "best fit", "which should i lead with",
      "which should i recommend", "recommend"], "top_picks"),

    # Spec follow-ups (micron, temp, pressure, flow) — reuse top_picks which
    # already has specs in the JSON output
    (["micron", "micron rating", "spec", "specs", "specifications",
      "flow rate", "temperature", "temp", "psi", "max pressure", "details",
      "detail"], "top_picks"),

    # Price follow-ups — reuse top_picks (already includes prices)
    (["price", "prices", "pricing", "cost", "how much", "what do they cost"], "top_picks"),

    # Stock / warehouse follow-ups — reuse top_picks (already includes stock)
    (["in stock", "stock", "available", "houston", "kansas city", "charlotte",
      "warehouse", "location", "where are they", "any stock"], "top_picks"),

    # Alternatives / supplier / "more of the same"
    (["alternative", "alternatives", "other option", "other options", "backup",
      "substitute", "other brand", "other brands", "other manufacturer",
      "more parts", "more from", "from that supplier", "from that manufacturer",
      "same supplier", "same manufacturer"], "alternatives"),

    # Pregame summary / briefing
    (["pregame", "summary", "brief me", "prep me", "walk me through",
      "recap", "overview"], "pregame_summary"),

    # Questions to ask
    (["questions", "what to ask", "what should i ask", "what do i ask",
      "prepare me", "what should i know", "what else"], "questions_to_ask"),

    # Risk flags / concerns / escalation
    (["risk", "flag", "concern", "warning", "watch out", "red flag",
      "anything to worry", "escalation", "safety"], "risk_flags"),

    # Cross-sell / pairing
    (["cross sell", "cross-sell", "pair with", "goes with", "upsell",
      "what goes with", "related products", "housing", "what else do they need"], "cross_sell"),

    # Next likely questions
    (["what's next", "whats next", "next question", "what comes after",
      "anything else i should ask"], "scenario_next"),
]


def match_turn2_branch(user_message: str) -> Optional[str]:
    """Match a follow-up message to a cached branch key."""
    msg = user_message.lower().strip()
    for phrases, branch_key in TURN2_BRANCH_MAP:
        if any(phrase in msg for phrase in phrases):
            return branch_key
    return None


def handle_turn2(session_id: str, user_message: str) -> Optional[dict[str, Any]]:
    """
    Check if we have cached context for this session AND the user's message
    matches one of the 8 pre-computed branches. If yes, return the cached
    answer instantly. If no, return None (caller falls through to live handler).
    """
    ctx = get_context(session_id)
    if not ctx:
        return None

    branch_key = match_turn2_branch(user_message)
    if not branch_key:
        return None

    reasoning = ctx.get("reasoning", {})
    cached_answer = reasoning.get(branch_key, "").strip()
    if not cached_answer:
        return None

    logger.info(f"[turn2] cache HIT session={session_id[:12]} branch={branch_key}")
    return {
        "response": cached_answer,
        "products": ctx.get("candidates", [])[:5],
        "intent": "pregame_followup",
        "cost": "$0 (cached)",
        "context_key": session_id,
        "cache_hit": True,
        "branch": branch_key,
    }
