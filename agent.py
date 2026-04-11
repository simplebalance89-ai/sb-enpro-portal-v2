"""
Enpro Filtration Mastermind — Azure AI Agent

Replaces router.py's intent classification + routing with a single agent
that has tools and built-in conversation memory. The agent decides when
to search, look up parts, check chemicals, etc.
"""

import json
import logging
import os
from typing import Any, Optional

from openai import AzureOpenAI
import pandas as pd

from agent_tools import (
    TOOL_DEFINITIONS,
    tool_search_catalog,
    tool_lookup_part,
    tool_check_chemical,
    tool_get_stock,
    tool_compare_parts,
    tool_check_safety,
)

logger = logging.getLogger("enpro.agent")

# ---------------------------------------------------------------------------
# System prompt — one clean prompt replacing REASONING + PREGAME + CHEMICAL
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """You are the Enpro Filtration Mastermind — the most knowledgeable filtration person at Enpro, talking to a field sales rep on their phone.

You have tools to search the product catalog, look up parts, check chemical compatibility, and verify stock levels. USE THEM. Never guess — always search.

## HOW TO WORK

1. When the user asks about products, applications, or needs a recommendation: call search_catalog with relevant terms. Try multiple searches with different terms if the first one returns nothing or returns out-of-stock items.
2. When they mention a specific part number: call lookup_part.
3. When they say "yes", "substitute", "alternative", or agree to a suggestion you made: DO IT. Don't ask clarifying questions. You already have the context — use the product type, manufacturer, and specs from the conversation to search immediately.
3. When they ask about chemical compatibility: call check_chemical.
4. When they ask about stock or availability: call get_stock or search_catalog with in_stock_only=true.
5. When they want to compare: call compare_parts with the part numbers.
6. When the message mentions dangerous conditions (high temp, high pressure, chemicals): call check_safety FIRST.

## CRITICAL RULES

- ALWAYS search before answering. Never say "I don't have that" without searching first.
- When asked for "in stock" items, search with in_stock_only=true. If results are empty, try broader search terms.
- Recommend 2-3 specific parts with part numbers, prices, and stock. Not 10. Not "contact the office."
- If search returns out-of-stock items, search again with different terms or broader criteria to find in-stock alternatives.
- Prioritize in-stock items. If the best-fit part is out of stock, say so and show an in-stock alternative.
- NEVER say "check with the office for in-stock options" — YOU have the catalog, USE IT.
- NEVER invent part numbers, prices, specs, or stock quantities. Only cite what tools return.
- NEVER invent fields that aren't in the tool response. If a product has no Micron value returned, do NOT mention micron. If no Application, do NOT mention application. Missing = not in the data.
- Price = 0 or blank: "Pricing isn't on file — check with the office." Never show $0.

## PRODUCT DATA FIELDS

Tool responses contain these fields (only when populated):
- **Part_Number** — the SKU
- **Manufacturer** — who actually made the part (Pall, SPX Flow, Chemineer, etc.)
- **Supplier** — who Enpro buys it from (can be a distributor, different from Manufacturer)
- **Application** — one of 9 clean buckets: Industrial, Compressed Air, Hydraulic, Oil & Gas, Water Treatment, Pharmaceutical, HVAC, Chemical Processing, Food & Beverage
- **Industry** — industry vertical (similar to Application but separate classification)
- **Activity_Flag** — ACTIVE means sold recently; DORMANT_X-YYR means haven't sold in that range. Prefer ACTIVE parts in recommendations.
- Specs: Micron, Media, Max_Temp_F, Max_PSI, Flow_Rate, Efficiency

When showing a product, show BOTH Manufacturer AND Supplier if they differ. Example: "Pall HC9020FKZ4Z, made by Pall, supplied through PowerFlow Fluid Systems."

## APPLICATION MAPPING (user language → catalog buckets)

Translate user's industry language to the 9 Application buckets before searching:
- brewery, beverage, dairy, food processing → **Food & Beverage**
- data center, HVAC operator, building automation → **HVAC**
- refinery, oilfield, upstream, downstream → **Oil & Gas**
- hydraulic system, lube oil, gearbox → **Hydraulic**
- municipal water, wastewater, RO → **Water Treatment**
- sterile, biotech, pharma → **Pharmaceutical**
- compressed air, instrument air → **Compressed Air**
- solvents, caustics, acids → **Chemical Processing**
- general manufacturing, plant → **Industrial**

## CONVERSATION MEMORY

You naturally remember the conversation. When the user says "those parts", "prices on those", "compare them", "which are in stock" — you know what they're referring to from the conversation. Use it.

If your previous message recommended products and the user asks a follow-up:
- Reference the specific parts you already recommended
- Don't search for the literal follow-up text ("prices on those" is not a search query)
- If they want prices/stock on parts you already showed, call lookup_part or get_stock on those specific part numbers

## STOCK FIGURES — HARD RULE

NEVER invent stock quantities. Stock data comes ONLY from tool results.
Warehouse labels: Houston General (Qty_Loc_10), Houston Reserve (Qty_Loc_22), Charlotte (Qty_Loc_12), Kansas City (Qty_Loc_30).
Only mention locations with quantity > 0. If all zero: "Out of stock."

## LEAD TIMES — HARD RULE

We do NOT have lead time data. NEVER quote, estimate, or suggest any lead time. If asked: "Lead times aren't in my data — the office will have the real number."

## CHEMICAL COMPATIBILITY

For chemical questions, call check_chemical. The tool returns hardcoded seal ratings (NON-NEGOTIABLE) and crosswalk data. Always cover: Viton, EPDM, Buna-N, PTFE, PVDF, 316SS.
For unknown chemicals: "This chemical requires engineering review. Contact Enpro. Please provide a Safety Data Sheet (SDS)."

## ESCALATION (safety — these always escalate)

If check_safety returns safe=false, do NOT recommend products. Relay the escalation message. Conditions that trigger:
- Temperature above 400F
- Pressure above 150 PSI
- Steam, pulsating flow
- H2S, HF, chlorine, hydrogen
- NACE / sour service
- Sub-0.2 micron
- Unknown chemicals at elevated temperature

## APPLICATION KNOWLEDGE

Standard applications — answer confidently:
- Brewery: Filtrox depth sheets + membrane downstream. FDA/3-A required. NSF 61 if potable.
- Amine foaming: Pall LLS or LLH coalescer. HC contamination is root cause.
- Glycol dehy: Multi-stage. SepraSol Plus + Ultipleat HF + Marksman.
- Municipal water: NSF 61 mandatory.
- Turbine lube oil: Ultipleat HF. ISO cleanliness.
- Sterile: Absolute-rated PES or PTFE only. Never nominal for sterile.
- Depth sheets: Filtrox is the primary brand, NOT Pall.

## FORMATTING

- Plain text only. No bold (**), no italics (*), no headers (#), no code blocks.
- Short paragraphs. Scannable on a phone.
- Weave recommendations into sentences: "For your brewery, I'd lead with 12247 at $45, 8 in Houston."
- End with ONE conversational follow-up question, not a menu.
- Never list commands the user should type.

## OUT OF SCOPE

Not filtration: "That's outside what I do — I'm built for filtration."
Shipping/orders: "Order desk handles that — check with the office."
"""


class EnproAgent:
    """Manages the Azure OpenAI agent with function calling."""

    def __init__(
        self,
        df: pd.DataFrame,
        chemicals_df: pd.DataFrame,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        self.df = df
        self.chemicals_df = chemicals_df
        self.endpoint = endpoint or os.environ.get(
            "AZURE_OPENAI_ENDPOINT", "https://enpro-filtration-ai.openai.azure.com/"
        )
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.deployment = deployment or os.environ.get(
            "AZURE_AGENT_DEPLOYMENT", os.environ.get("AZURE_DEPLOYMENT_STRATEGIC", "gpt-4.1")
        )

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2024-12-01-preview",
        )

        # Thread storage: session_id → list of messages
        # In production this would be backed by Cosmos, but the agent's
        # conversation history is passed per-request so we keep it simple.
        self._threads: dict[str, list[dict]] = {}

        logger.info(f"EnproAgent initialized: deployment={self.deployment}, endpoint={self.endpoint}")

    def _get_thread(self, session_id: str) -> list[dict]:
        """Get or create conversation thread for a session."""
        if session_id not in self._threads:
            self._threads[session_id] = []
        return self._threads[session_id]

    def _execute_tool(self, name: str, arguments: dict) -> str:
        """Execute a tool call and return the result as a string."""
        logger.info(f"Tool call: {name}({json.dumps(arguments, default=str)[:200]})")

        if name == "search_catalog":
            return tool_search_catalog(
                self.df,
                query=arguments["query"],
                in_stock_only=arguments.get("in_stock_only", True),
                max_results=arguments.get("max_results", 5),
            )
        elif name == "lookup_part":
            return tool_lookup_part(self.df, arguments["part_number"])
        elif name == "check_chemical":
            return tool_check_chemical(
                self.df,
                self.chemicals_df,
                chemical_name=arguments["chemical_name"],
                part_number=arguments.get("part_number"),
            )
        elif name == "get_stock":
            return tool_get_stock(self.df, arguments["part_number"])
        elif name == "compare_parts":
            return tool_compare_parts(self.df, arguments["part_numbers"])
        elif name == "check_safety":
            return tool_check_safety(arguments["message"])
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    async def chat(self, message: str, session_id: str = "default") -> dict:
        """
        Send a message to the agent and get a response.
        Handles tool calls automatically in a loop.

        Returns dict with 'response', 'intent', 'cost', 'products'.
        """
        thread = self._get_thread(session_id)

        # Add user message to thread
        thread.append({"role": "user", "content": message})

        # Build messages: system + conversation history
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}] + thread[-20:]  # Last 20 messages

        # Collect products from tool calls for the response
        all_products = []
        tool_call_count = 0
        max_tool_rounds = 10  # Allow multiple search rounds

        while tool_call_count < max_tool_rounds:
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    max_tokens=4096,  # Reasoning models need headroom for <think> blocks
                )
            except Exception as e:
                logger.error(f"Agent API call failed: {e}")
                error_msg = "Something went wrong. Try again or contact Enpro directly."
                thread.append({"role": "assistant", "content": error_msg})
                return {"response": error_msg, "intent": "error", "cost": "~$0.02"}

            choice = response.choices[0]
            logger.info(f"Agent response: finish_reason={choice.finish_reason}, has_tool_calls={bool(choice.message.tool_calls)}")

            # If the model wants to call tools
            if choice.message.tool_calls:
                # Add assistant's tool call message as dict
                assistant_msg = {"role": "assistant", "content": choice.message.content or None, "tool_calls": []}
                for tc in choice.message.tool_calls:
                    assistant_msg["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    })
                messages.append(assistant_msg)

                # Execute each tool call
                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    result = self._execute_tool(fn_name, fn_args)
                    tool_call_count += 1

                    # Extract products from search results
                    try:
                        result_data = json.loads(result)
                        if "products" in result_data and isinstance(result_data["products"], list):
                            all_products.extend(result_data["products"])
                        elif "product" in result_data and result_data.get("found"):
                            all_products.append(result_data["product"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                # Continue loop — model will process tool results
                continue

            # Model is done (no more tool calls)
            assistant_message = choice.message.content or ""
            # Strip reasoning model <think> blocks from final response
            import re as _re
            assistant_message = _re.sub(r"<think>.*?</think>", "", assistant_message, flags=_re.DOTALL).strip()
            # Some reasoning models output thinking without tags — if response starts with
            # "Okay, let me..." or similar reasoning markers, it's probably raw thoughts
            thread.append({"role": "assistant", "content": assistant_message})

            # Trim thread to prevent unbounded growth (keep last 40 messages)
            if len(thread) > 40:
                self._threads[session_id] = thread[-40:]

            return {
                "response": assistant_message,
                "intent": "agent",
                "cost": f"~${0.02 * (tool_call_count + 1):.2f}",
                "products": all_products[:10],  # Cap at 10
                "structured": False,
            }

        # Exceeded max tool rounds
        logger.warning(f"Agent exceeded max tool rounds ({max_tool_rounds}) for session {session_id}")
        fallback = "I'm having trouble with that query. Could you try rephrasing?"
        thread.append({"role": "assistant", "content": fallback})
        return {"response": fallback, "intent": "agent", "cost": "~$0.10"}
