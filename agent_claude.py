"""
Enpro Filtration Mastermind — Claude Agent (direct Anthropic API)

Drop-in replacement for EnproAgent that calls Claude directly via
api.anthropic.com instead of Azure OpenAI. Same tool set, same system
prompt, same session threading — just the model and API layer differs.

Why: Claude Opus 4.6 / Sonnet 4.6 chains multi-turn conversations with
structured data (matrix reads, compare flows, pregame synthesis) far
more reliably than gpt-4o in testing. Peter proved this in Edge Crew v3
and in a ChatGPT custom GPT before that.

Anthropic isn't in the Azure Foundry catalog, and the Marketplace SaaS
offer is a Portal-only dance. Direct API is faster and matches the
pattern Edge Crew v3 already uses in production.
"""

import json
import logging
import os
import re
from typing import Any, Optional

import httpx
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
# Reuse the exact same system prompt so behavior is identical
from agent import AGENT_SYSTEM_PROMPT

logger = logging.getLogger("enpro.agent_claude")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-5"  # Claude Opus 4.5 is the current production model
DEFAULT_MAX_TOKENS = 4096


def _convert_tools_to_anthropic(openai_tools: list) -> list:
    """
    Convert OpenAI function-calling tool definitions to Anthropic's format.

    OpenAI format:
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}

    Anthropic format:
        {"name": ..., "description": ..., "input_schema": {...}}
    """
    result = []
    for tool in openai_tools:
        if tool.get("type") != "function":
            continue
        fn = tool.get("function", {})
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


class EnproClaudeAgent:
    """Claude-powered agent using Anthropic's direct API."""

    def __init__(
        self,
        df: pd.DataFrame,
        chemicals_df: pd.DataFrame,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.df = df
        self.chemicals_df = chemicals_df
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("AZURE_AGENT_DEPLOYMENT", DEFAULT_MODEL)
        # If someone set the Azure-style name, normalize to Anthropic's expected name
        if self.model == "claude-opus-4-6":
            self.model = "claude-opus-4-5"  # current Anthropic production name
        self.max_tokens = max_tokens

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        # Pre-convert tools once
        self.anthropic_tools = _convert_tools_to_anthropic(TOOL_DEFINITIONS)

        # Session threads — same shape as EnproAgent
        self._threads: dict[str, list[dict]] = {}

        logger.info(
            f"EnproClaudeAgent initialized: model={self.model}, "
            f"tools={len(self.anthropic_tools)}, max_tokens={self.max_tokens}"
        )

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

    async def _call_claude(self, messages: list[dict]) -> dict:
        """
        Make a single call to Anthropic's messages API.

        Returns the raw response dict.
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": AGENT_SYSTEM_PROMPT,
            "tools": self.anthropic_tools,
            "messages": messages,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:500]}")
            return resp.json()

    async def chat(self, message: str, session_id: str = "default") -> dict:
        """
        Send a message to Claude and get a response.
        Handles tool calls automatically in a loop.

        Returns dict with 'response', 'intent', 'cost', 'products', 'structured'.
        """
        thread = self._get_thread(session_id)

        # Add user message to thread (Anthropic format: role + content)
        thread.append({"role": "user", "content": message})

        # Trim thread to last 20 messages to keep context reasonable
        messages = thread[-20:]

        all_products = []
        tool_call_count = 0
        max_tool_rounds = 15

        while tool_call_count < max_tool_rounds:
            try:
                response = await self._call_claude(messages)
            except Exception as e:
                logger.error(f"Claude API call failed: {e}")
                error_msg = "Something went wrong. Try again or contact Enpro directly."
                thread.append({"role": "assistant", "content": error_msg})
                return {"response": error_msg, "intent": "error", "cost": "~$0.05"}

            stop_reason = response.get("stop_reason", "")
            content_blocks = response.get("content", [])

            # Separate text blocks and tool_use blocks
            text_blocks = [b for b in content_blocks if b.get("type") == "text"]
            tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

            logger.info(
                f"Claude response: stop_reason={stop_reason}, "
                f"text_blocks={len(text_blocks)}, tool_uses={len(tool_uses)}"
            )

            # If Claude wants to use tools, execute them and continue the loop
            if tool_uses:
                # Add the full assistant message (with tool_use blocks) to history
                messages.append({"role": "assistant", "content": content_blocks})

                # Execute each tool and build the tool_result blocks
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use.get("name", "")
                    tool_input = tool_use.get("input", {}) or {}
                    tool_id = tool_use.get("id", "")

                    result = self._execute_tool(tool_name, tool_input)
                    tool_call_count += 1

                    # Extract products from the result for the UI response payload
                    try:
                        result_data = json.loads(result)
                        if isinstance(result_data, dict):
                            if "products" in result_data and isinstance(result_data["products"], list):
                                all_products.extend(result_data["products"])
                            elif "product" in result_data and result_data.get("found"):
                                all_products.append(result_data["product"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    })

                # Send tool results back as a user message (Anthropic's format)
                messages.append({"role": "user", "content": tool_results})
                continue

            # No tool calls — we have the final response
            final_text = "\n\n".join(b.get("text", "") for b in text_blocks).strip()

            # Strip any <think> or reasoning tags (defensive — Claude generally doesn't do this)
            final_text = re.sub(r"<think>.*?</think>", "", final_text, flags=re.DOTALL).strip()

            # Persist only simple user/assistant text pairs back into the session thread
            # (we drop the full tool_use/tool_result blocks so the next turn starts clean
            # and the next call re-resolves context via the simplified history)
            # Find the user message we just added and keep everything prior intact
            # while overwriting the assistant turn with the final text only.
            thread.append({"role": "assistant", "content": final_text})

            # Trim stored thread (simple text-only form) to keep it from growing unbounded
            if len(thread) > 40:
                self._threads[session_id] = thread[-40:]

            return {
                "response": final_text,
                "intent": "agent",
                "cost": f"~${0.015 * (tool_call_count + 1):.2f}",
                "products": all_products[:10],
                "structured": False,
            }

        # Exceeded max tool rounds
        logger.warning(f"Claude agent exceeded max tool rounds ({max_tool_rounds}) for session {session_id}")
        fallback = "I'm having trouble with that query. Could you try rephrasing?"
        thread.append({"role": "assistant", "content": fallback})
        return {"response": fallback, "intent": "agent", "cost": "~$0.15"}
