"""
Pregame Pipeline Prompts — 8 narrow parallel reasoning tasks.

Each prompt is a narrow, focused job that runs in parallel against the
SAME pre-filtered candidate set. The model does NOT search the catalog —
it grades/compares/ranks/writes based on what pandas already fetched.

Pattern: Edge Crew v3 crowdsource_grade. Each call has ONE job, not a
conversation. Results are aggregated and cached for Turn 2 follow-ups.
"""

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

YOUR JOB:
"""


# ---------------------------------------------------------------------------
# The 8 narrow reasoning prompts
# ---------------------------------------------------------------------------

PROMPT_TOP_PICKS = """Pick the TOP 3 parts from the candidate set that best fit this
customer's application.

For each pick, give:
- Part number
- ONE sentence of plain-text reasoning (why this part fits THIS customer)
- Price + stock location from the data

Return as a JSON array of 3 objects with keys: part_number, reason, price, stock_location.

Rules:
- Only use part numbers that appear in the candidate set above.
- Never invent specs, prices, or stock figures.
- If the candidate set has fewer than 3 good fits, return fewer picks and explain why.
"""


PROMPT_COMPARE_TOP_2 = """Compare the TOP 2 candidates side by side.

Return a JSON object with keys:
- part_a: {part_number, description, key_specs, price, stock}
- part_b: {part_number, description, key_specs, price, stock}
- differences: array of 3-5 short strings naming specific differences
- recommendation: one sentence — which one and why

Rules:
- Only use candidate-set data. No invented specs.
- If specs are missing, say "not in catalog" — don't guess.
"""


PROMPT_PREGAME_SUMMARY = """Write a 3-5 sentence conversational briefing for the
sales rep to read on their phone before the customer meeting.

Format: plain text, no markdown, no bullets, no headers.

Cover:
- What this customer type cares about most
- The top 1-2 parts you'd lead with from the candidate set (by part number)
- One concern or constraint to watch for

Tone: colleague briefing, not a data dump. Weave part numbers and prices into
sentences naturally. Example: "For your brewery meeting, I'd lead with
FD-AF0110-16 — Filtrox 2 micron depth sheet, 8 in Houston at $45 each — it's
what breweries run for clarification before the membrane stage."

Rules:
- Only use candidate-set data.
- NEVER mention lead times (we don't have that data).
- Never say "check with the office" — that's a cop-out.
"""


PROMPT_QUESTIONS_TO_ASK = """Write the 4 most useful questions the sales rep should
ask this customer to qualify the opportunity.

Return a JSON array of 4 short question strings.

Rules:
- Questions should be specific to THIS application and THIS candidate set.
- Never generic like "what are your filtration needs?"
- Examples for brewery: "What's your current clarity target — visual or NTU?"
  "Are you filtering wort, beer, or finished product?"
"""


PROMPT_ALTERNATIVES = """Identify 2-3 alternative parts from the candidate set that
could serve as backup if the top picks aren't a fit.

Return JSON array with: part_number, why_it_could_work (one sentence),
when_to_suggest (one sentence — what the customer would need to say for this
to become the lead pick instead).

Rules:
- Only use parts from the candidate set.
- Don't repeat the top picks.
"""


PROMPT_RISK_FLAGS = """Scan the customer context and the candidate set for ANY risk flags
the rep should know about before the meeting.

Look for:
- Escalation triggers (temp > 400F, pressure > 150 PSI, H2S, hydrogen, NACE)
- Certification gaps (FDA/3-A/NSF if food/beverage/pharma)
- Out-of-stock on the best-fit parts
- Compatibility concerns

Return JSON array of flag objects: {severity: "high"|"medium"|"low", flag: "short string", reason: "one sentence"}.

Rules:
- Only flag things supported by the data.
- If no flags, return an empty array — don't invent concerns.
"""


PROMPT_CROSS_SELL = """Identify cross-sell or up-sell opportunities for this meeting.

Look at the candidate set for:
- Housings that pair with the top-pick elements
- Upstream/downstream stage products (pre-filter, final filter)
- Replacement or consumable cycles

Return JSON array of: {part_number, opportunity_type, pitch_in_one_sentence}.

Rules:
- Only use parts from the candidate set.
- If there's no clear cross-sell, return an empty array.
"""


PROMPT_SCENARIO_NEXT = """Predict the 5 most likely NEXT questions this rep will ask
based on Turn 1 context.

Return JSON array of 5 strings — the literal next questions the rep is probably
going to type or say. Be concrete and specific to this application.

Example outputs for brewery pregame:
- "what are the prices on those"
- "which ones are in stock in Houston"
- "compare the top two"
- "what micron for sterile filtration"
- "alternatives from a different manufacturer"

Rules:
- Make them sound like how a rep actually talks.
- Order by probability (most likely first).
"""


# Branch key → prompt template. Used by pregame_pipeline to fan out.
PROMPTS = {
    "top_picks": PROMPT_TOP_PICKS,
    "compare_top_2": PROMPT_COMPARE_TOP_2,
    "pregame_summary": PROMPT_PREGAME_SUMMARY,
    "questions_to_ask": PROMPT_QUESTIONS_TO_ASK,
    "alternatives": PROMPT_ALTERNATIVES,
    "risk_flags": PROMPT_RISK_FLAGS,
    "cross_sell": PROMPT_CROSS_SELL,
    "scenario_next": PROMPT_SCENARIO_NEXT,
}


def build_full_prompt(
    branch_key: str,
    customer_context: str,
    application: str,
    kb_context: str,
    candidates_json: str,
) -> str:
    """Assemble the full prompt for one parallel reasoning call."""
    body = PROMPTS.get(branch_key, "")
    if not body:
        return ""
    header = CONTEXT_HEADER.format(
        customer_context=customer_context or "(not provided)",
        application=application or "(unknown)",
        kb_context=kb_context or "(no KB entry for this application)",
        candidates_json=candidates_json or "[]",
    )
    return header + body
