"""
Pregame Pipeline Prompts — 8 narrow parallel reasoning tasks.

Each branch is exposed as an Anthropic tool with a strict input_schema.
The pipeline forces the model to use that one tool via tool_choice, so the
model cannot return prose, cannot omit fields, and cannot smuggle extra
keys. Schema enforcement happens in the Anthropic API, not in regex on
our side.

Pattern: Edge Crew v3 crowdsource_grade, tightened with tool use so Turn 2
cache hits always receive structured data instead of hoping a prose JSON
block parses cleanly.

Public API (consumed by pregame_pipeline.py):
    TOOLS            — dict[branch_key] -> Anthropic tool schema
    CONTEXT_HEADER   — shared context template (customer + app + kb + candidates)
    build_user_message(branch_key, **ctx) -> str
                     — user-facing instruction that tells Claude which tool to use
    render_branch(branch_key, tool_input) -> str
                     — render the tool's structured output into a human-readable string
                       for Turn 1 display and Turn 2 cache hits

The old PROMPTS dict and build_full_prompt() are kept as thin shims so any
legacy caller still works, but they delegate to the tool-use path.
"""

from typing import Any


# ---------------------------------------------------------------------------
# Shared context template (prepended to every parallel prompt)
# ---------------------------------------------------------------------------

CONTEXT_HEADER = """You are grading filtration products for an Enpro sales rep
preparing for a customer meeting.

CUSTOMER CONTEXT:
{customer_context}

APPLICATION: {application}

KNOWLEDGE BASE (from John's technical documents):
{kb_context}

CANDIDATES (already filtered by Application + Item_Category=OK-FILTRATION
+ ACTIVE status + in-stock, sorted by priority):
{candidates_json}

---
"""


# ---------------------------------------------------------------------------
# The 8 tool schemas — one per branch, strictly typed
# ---------------------------------------------------------------------------
#
# Every tool's description carries the same rule preamble the old prose
# prompts used. The input_schema is what Claude is forced to match.

_RULES_PREAMBLE = (
    "Only use part numbers that appear in the candidate set above. "
    "Never invent specs, prices, or stock figures. "
    "If a field is missing from the candidate data, use the string 'not in catalog'."
)


TOOLS: dict[str, dict[str, Any]] = {
    "top_picks": {
        "name": "return_top_picks",
        "description": (
            "Pick the top 3 parts from the candidate set that best fit this customer's "
            "application. For each pick give the part number, one sentence of reasoning, "
            "the price, and the stock location from the data. If the candidate set has "
            "fewer than 3 good fits, return fewer picks. " + _RULES_PREAMBLE
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "picks": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number": {"type": "string"},
                            "reason": {"type": "string", "description": "One sentence plain-text reasoning"},
                            "price": {"type": "string"},
                            "stock_location": {"type": "string"},
                        },
                        "required": ["part_number", "reason", "price", "stock_location"],
                    },
                },
            },
            "required": ["picks"],
        },
    },

    "compare_top_2": {
        "name": "return_compare_top_2",
        "description": (
            "Compare the top 2 candidates side by side. Pull description, key specs, "
            "price, and stock from the data. List 3-5 specific differences. End with a "
            "one-sentence recommendation. " + _RULES_PREAMBLE
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "part_a": {
                    "type": "object",
                    "properties": {
                        "part_number": {"type": "string"},
                        "description": {"type": "string"},
                        "key_specs": {"type": "string"},
                        "price": {"type": "string"},
                        "stock": {"type": "string"},
                    },
                    "required": ["part_number", "description", "key_specs", "price", "stock"],
                },
                "part_b": {
                    "type": "object",
                    "properties": {
                        "part_number": {"type": "string"},
                        "description": {"type": "string"},
                        "key_specs": {"type": "string"},
                        "price": {"type": "string"},
                        "stock": {"type": "string"},
                    },
                    "required": ["part_number", "description", "key_specs", "price", "stock"],
                },
                "differences": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
                "recommendation": {"type": "string"},
            },
            "required": ["part_a", "part_b", "differences", "recommendation"],
        },
    },

    "pregame_summary": {
        "name": "return_pregame_summary",
        "description": (
            "Write a 3-5 sentence conversational briefing for the sales rep to read on "
            "their phone before the customer meeting. Plain text only, no markdown, "
            "no bullets. Cover what this customer type cares about most, the top 1-2 "
            "parts to lead with (by part number), and one concern or constraint. "
            "Weave part numbers and prices into sentences naturally. Never mention "
            "lead times. Never say 'check with the office'. " + _RULES_PREAMBLE
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "briefing": {
                    "type": "string",
                    "description": "3-5 sentence plain-text conversational briefing",
                },
            },
            "required": ["briefing"],
        },
    },

    "questions_to_ask": {
        "name": "return_questions_to_ask",
        "description": (
            "Write the 4 most useful questions the sales rep should ask this customer "
            "to qualify the opportunity. Questions must be specific to THIS application "
            "and THIS candidate set — never generic like 'what are your filtration needs'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": {"type": "string"},
                },
            },
            "required": ["questions"],
        },
    },

    "alternatives": {
        "name": "return_alternatives",
        "description": (
            "Identify 2-3 alternative parts from the candidate set that could serve as "
            "backup if the top picks aren't a fit. Each needs a one-sentence reason "
            "and a one-sentence trigger (what the customer would need to say for this "
            "to become the lead pick). Don't repeat the top picks. " + _RULES_PREAMBLE
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alternatives": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number": {"type": "string"},
                            "why_it_could_work": {"type": "string"},
                            "when_to_suggest": {"type": "string"},
                        },
                        "required": ["part_number", "why_it_could_work", "when_to_suggest"],
                    },
                },
            },
            "required": ["alternatives"],
        },
    },

    "risk_flags": {
        "name": "return_risk_flags",
        "description": (
            "Scan the customer context and the candidate set for any risk flags the rep "
            "should know before the meeting. Look for escalation triggers (temp > 400F, "
            "pressure > 150 PSI, H2S, hydrogen, NACE), certification gaps "
            "(FDA/3-A/NSF for food/beverage/pharma), out-of-stock on best-fit parts, "
            "and compatibility concerns. If no flags, return an empty array — don't "
            "invent concerns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                            "flag": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["severity", "flag", "reason"],
                    },
                },
            },
            "required": ["flags"],
        },
    },

    "cross_sell": {
        "name": "return_cross_sell",
        "description": (
            "Identify cross-sell or up-sell opportunities for this meeting. Look at the "
            "candidate set for housings that pair with the top-pick elements, "
            "upstream/downstream stage products (pre-filter, final filter), and "
            "replacement or consumable cycles. If there's no clear cross-sell, return "
            "an empty array. " + _RULES_PREAMBLE
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "opportunities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number": {"type": "string"},
                            "opportunity_type": {"type": "string"},
                            "pitch_in_one_sentence": {"type": "string"},
                        },
                        "required": ["part_number", "opportunity_type", "pitch_in_one_sentence"],
                    },
                },
            },
            "required": ["opportunities"],
        },
    },

    "scenario_next": {
        "name": "return_scenario_next",
        "description": (
            "Predict the 5 most likely next questions this rep will ask based on Turn 1 "
            "context. Make them sound like how a rep actually talks — concrete and "
            "specific to this application. Order by probability (most likely first)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "next_questions": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
            },
            "required": ["next_questions"],
        },
    },
}


# ---------------------------------------------------------------------------
# User message builder — context header + instruction to use the tool
# ---------------------------------------------------------------------------

def build_user_message(
    branch_key: str,
    customer_context: str,
    application: str,
    kb_context: str,
    candidates_json: str,
) -> str:
    """
    Build the user message sent with a forced tool_choice for one branch.

    The context header is shared; the tail tells Claude which tool to use.
    Actual output enforcement happens via tool_choice + input_schema, so we
    don't repeat rules here — they're in the tool description.
    """
    tool = TOOLS.get(branch_key)
    if not tool:
        return ""
    header = CONTEXT_HEADER.format(
        customer_context=customer_context or "(not provided)",
        application=application or "(unknown)",
        kb_context=kb_context or "(no KB entry for this application)",
        candidates_json=candidates_json or "[]",
    )
    return header + f"Use the {tool['name']} tool to respond."


# ---------------------------------------------------------------------------
# Render the tool's structured output into a human-readable string
# ---------------------------------------------------------------------------
# Used for Turn 1 display and Turn 2 cache hits. Keeps reasoning[key] as a
# string so downstream code (server.py _chat_stream_generator, handle_turn2)
# doesn't need to change.

def _render_top_picks(data: dict) -> str:
    picks = data.get("picks", []) or []
    if not picks:
        return "No top picks available from the candidate set."
    lines = []
    for i, p in enumerate(picks, 1):
        pn = p.get("part_number", "?")
        reason = p.get("reason", "")
        price = p.get("price", "")
        stock = p.get("stock_location", "")
        tail_bits = [b for b in [price, stock] if b and b != "not in catalog"]
        tail = f" ({'; '.join(tail_bits)})" if tail_bits else ""
        lines.append(f"{i}. {pn} — {reason}{tail}")
    return "\n".join(lines)


def _render_compare_top_2(data: dict) -> str:
    a = data.get("part_a") or {}
    b = data.get("part_b") or {}
    diffs = data.get("differences") or []
    rec = data.get("recommendation", "")
    lines = []
    lines.append(f"Part A: {a.get('part_number','?')} — {a.get('description','')}")
    lines.append(f"  Specs: {a.get('key_specs','')}")
    lines.append(f"  Price: {a.get('price','')}, Stock: {a.get('stock','')}")
    lines.append("")
    lines.append(f"Part B: {b.get('part_number','?')} — {b.get('description','')}")
    lines.append(f"  Specs: {b.get('key_specs','')}")
    lines.append(f"  Price: {b.get('price','')}, Stock: {b.get('stock','')}")
    if diffs:
        lines.append("")
        lines.append("Differences:")
        for d in diffs:
            lines.append(f"  - {d}")
    if rec:
        lines.append("")
        lines.append(f"Recommendation: {rec}")
    return "\n".join(lines)


def _render_pregame_summary(data: dict) -> str:
    return (data.get("briefing") or "").strip()


def _render_questions_to_ask(data: dict) -> str:
    qs = data.get("questions") or []
    if not qs:
        return "No qualifying questions."
    return "\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1))


def _render_alternatives(data: dict) -> str:
    alts = data.get("alternatives") or []
    if not alts:
        return "No alternatives from the candidate set."
    lines = []
    for i, a in enumerate(alts, 1):
        pn = a.get("part_number", "?")
        why = a.get("why_it_could_work", "")
        when = a.get("when_to_suggest", "")
        lines.append(f"{i}. {pn} — {why} Use when: {when}")
    return "\n".join(lines)


def _render_risk_flags(data: dict) -> str:
    flags = data.get("flags") or []
    if not flags:
        return "No risk flags."
    lines = []
    for f in flags:
        sev = (f.get("severity") or "").upper()
        flag = f.get("flag", "")
        reason = f.get("reason", "")
        lines.append(f"[{sev}] {flag} — {reason}")
    return "\n".join(lines)


def _render_cross_sell(data: dict) -> str:
    opps = data.get("opportunities") or []
    if not opps:
        return "No cross-sell opportunities in the candidate set."
    lines = []
    for i, o in enumerate(opps, 1):
        pn = o.get("part_number", "?")
        ot = o.get("opportunity_type", "")
        pitch = o.get("pitch_in_one_sentence", "")
        lines.append(f"{i}. {pn} ({ot}) — {pitch}")
    return "\n".join(lines)


def _render_scenario_next(data: dict) -> str:
    qs = data.get("next_questions") or []
    if not qs:
        return "No predicted follow-ups."
    return "\n".join(f'{i}. "{q}"' for i, q in enumerate(qs, 1))


_RENDERERS = {
    "top_picks": _render_top_picks,
    "compare_top_2": _render_compare_top_2,
    "pregame_summary": _render_pregame_summary,
    "questions_to_ask": _render_questions_to_ask,
    "alternatives": _render_alternatives,
    "risk_flags": _render_risk_flags,
    "cross_sell": _render_cross_sell,
    "scenario_next": _render_scenario_next,
}


def render_branch(branch_key: str, tool_input: dict) -> str:
    """
    Render a tool's structured output into the display string we cache as
    reasoning[branch_key]. Falls back to a safe placeholder if the branch is
    unknown or the data is malformed.
    """
    if not isinstance(tool_input, dict):
        return ""
    renderer = _RENDERERS.get(branch_key)
    if not renderer:
        return ""
    try:
        return renderer(tool_input) or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Legacy shims — kept so any old caller doesn't break.
# pregame_pipeline.py uses build_user_message() + TOOLS directly now.
# ---------------------------------------------------------------------------

PROMPTS = {key: TOOLS[key]["description"] for key in TOOLS}


def build_full_prompt(
    branch_key: str,
    customer_context: str,
    application: str,
    kb_context: str,
    candidates_json: str,
) -> str:
    """Legacy shim — delegates to build_user_message."""
    return build_user_message(
        branch_key=branch_key,
        customer_context=customer_context,
        application=application,
        kb_context=kb_context,
        candidates_json=candidates_json,
    )
