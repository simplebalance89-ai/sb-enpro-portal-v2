"""
Enpro Filtration Mastermind v3.0 - Unified Conversational AI
Replaces router.py (700 lines → 150 lines)

Key Changes:
- NO intent classification
- NO _handle_gpt() vs _handle_pandas() split
- ONE o3-mini call with reasoning
- Conversational tone (Andrew-approved)
"""

import json
import logging
from typing import List, Dict, Optional, Any
import pandas as pd

from azure.identity import DefaultAzureCredential
from azure_openai import AzureOpenAI

logger = logging.getLogger("enpro.mastermind_v3")

# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED SYSTEM PROMPT - The ONLY prompt you need
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_V3 = """You are the Enpro Filtration Mastermind — the most knowledgeable filtration expert at Enpro Submicron Filtration. You're texting with a field sales rep who's between customer meetings.

CRITICAL RULES (Never Break):
1. NEVER say "400 products found" or "I found 47 options" — ALWAYS narrow to 2-3 specific recommendations with reasoning
2. NEVER use command language like "say lookup" or "type compare" — just answer naturally
3. NEVER dump raw data — interpret it for the rep
4. ALWAYS ask ONE clarifying question if the request is ambiguous (not a list, ONE question)
5. ALWAYS carry context from previous messages — if they said "brewery" 2 turns ago, remember it
6. ALWAYS give reasoning: "I recommend X because Y" — reps need to explain to customers

CONVERSATION STYLE:
- Mobile-friendly short paragraphs (reps read on phones)
- Lead with the verdict: "For data center HVAC, I'd start with..."
- Reference context naturally: "Since you mentioned 10 micron last time..."
- Sound like a colleague who's been doing this 20 years, not a search engine

WHEN YOU NEED DATA:
If you need product information, respond with JSON:
{"tool_call": "search_products", "query": "your search query", "filters": {"application": "brewery", "micron": 10}}

If you need customer history:
{"tool_call": "get_customer", "customer_name": "Acme Brewing"}

If you need to check safety escalation:
{"tool_call": "check_escalation", "application_description": "..."}

AFTER YOU GET DATA:
Respond conversationally with your recommendations. Include:
- 2-3 specific part numbers with WHY each fits
- Price and stock if relevant
- ONE follow-up question to move the deal forward

TONE EXAMPLES:
❌ BAD: "I found 400 products. Say 'lookup HC9600' for details."
✅ GOOD: "For a brewery yeast application, I'd lead with Pall Supor PES 0.45 — absolute rated for consistency. If they want longer runs, the Graver PES is $12 less. What's their current change-out interval?"

❌ BAD: "Command: compare"
✅ GOOD: "HC9600 is Pall absolute-rated, $52, 12 in stock. CLR130 is PowerFlow nominal, $38, 45 in stock. The difference is absolute vs nominal — HC9600 if they need guaranteed 10 micron, CLR130 for general protection. Which matters more for this customer?"
"""

# ═══════════════════════════════════════════════════════════════════════════════
# MASTERMIND V3 - Unified Handler
# ═══════════════════════════════════════════════════════════════════════════════

class MastermindV3:
    """
    Unified conversational AI handler.
    
    Replaces:
    - router.py (intent classification)
    - All _handle_*() functions
    - 17 separate system prompts
    """
    
    def __init__(self, df: pd.DataFrame, customer_intel=None):
        self.df = df
        self.customer_intel = customer_intel
        
        # Azure OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint="https://enpro-filtration-ai.services.ai.azure.com/",
            api_version="2024-12-01-preview",
            credential=DefaultAzureCredential()
        )
        
        # Model deployment names (update these to match your Azure deployment)
        self.REASONING_MODEL = "o3-mini-high"  # Main reasoning
        self.FAST_MODEL = "gpt-5.4-mini"       # Narrowing selections
    
    async def chat(
        self,
        message: str,
        history: List[Dict] = None,
        customer_context: Dict = None
    ) -> Dict[str, Any]:
        """
        Single entry point for ALL conversations.
        
        Args:
            message: User's current message
            history: Last 5 conversation turns for context
            customer_context: Customer intel if available
        
        Returns:
            Dict with response and metadata
        """
        history = history or []
        
        # Build context-rich prompt
        context_parts = []
        
        if history:
            context_parts.append("CONVERSATION HISTORY:")
            for turn in history[-5:]:  # Last 5 turns
                role = "Rep" if turn.get("role") == "user" else "You"
                context_parts.append(f"{role}: {turn.get('content', '')[:200]}")
        
        if customer_context:
            context_parts.append(f"\nCUSTOMER CONTEXT: {json.dumps(customer_context, indent=2)}")
        
        context_parts.append(f"\nCURRENT MESSAGE: {message}")
        
        full_prompt = "\n".join(context_parts)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: o3-mini with reasoning (The ONLY model call for logic)
        # ═══════════════════════════════════════════════════════════════════
        logger.info(f"Processing: {message[:50]}...")
        
        response = self.client.chat.completions.create(
            model=self.REASONING_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_V3},
                {"role": "user", "content": full_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Handle tool calls (search, customer lookup, escalation)
        # ═══════════════════════════════════════════════════════════════════
        if "tool_call" in parsed:
            tool_result = await self._execute_tool(parsed["tool_call"], parsed.get("query", ""), parsed.get("filters", {}))
            
            # Second call with tool results
            final_response = self.client.chat.completions.create(
                model=self.REASONING_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_V3},
                    {"role": "user", "content": full_prompt},
                    {"role": "assistant", "content": response.choices[0].message.content},
                    {"role": "user", "content": f"Tool result: {json.dumps(tool_result)}"}
                ],
                response_format={"type": "json_object"}
            )
            
            parsed = json.loads(final_response.choices[0].message.content)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: Format response
        # ═══════════════════════════════════════════════════════════════════
        return {
            "response": parsed.get("response", parsed.get("to_user", "I'm thinking...")),
            "products": parsed.get("products_recommended", []),
            "follow_up": parsed.get("follow_up_question"),
            "escalation": parsed.get("escalation_triggered", False),
            "reasoning": parsed.get("thinking", "") if parsed.get("show_reasoning") else None,
            "model_used": self.REASONING_MODEL,
            "cost": self._estimate_cost(response.usage) if hasattr(response, 'usage') else 0.015
        }
    
    async def _execute_tool(self, tool_name: str, query: str, filters: Dict) -> Dict:
        """Execute tool calls from the model."""
        
        if tool_name == "search_products":
            return await self._search_products(query, filters)
        
        elif tool_name == "get_customer":
            return await self._get_customer(query)
        
        elif tool_name == "check_escalation":
            return self._check_escalation(query)
        
        return {"error": f"Unknown tool: {tool_name}"}
    
    async def _search_products(self, query: str, filters: Dict) -> Dict:
        """
        Search products and return TOP 3 ONLY (never more).
        Uses GPT-5.4-mini to narrow if needed.
        """
        # Your existing search logic (pandas for now)
        from search import search_products
        
        results = search_products(self.df, query)
        
        # If >5 results, use fast model to pick best 3
        if len(results) > 5:
            results = await self._narrow_to_three(query, results[:20], filters)
        else:
            results = results[:3]
        
        return {
            "count": len(results),
            "products": results.to_dict('records') if hasattr(results, 'to_dict') else results
        }
    
    async def _narrow_to_three(self, query: str, products: List[Dict], filters: Dict) -> List[Dict]:
        """
        Use GPT-5.4-mini ($0.003) to pick best 3 from 20.
        This is the secret sauce — no more "400 products found".
        """
        # Serialize products for the model
        product_summary = []
        for p in products[:20]:  # Top 20 only
            product_summary.append({
                "part_number": p.get("Part_Number"),
                "description": p.get("Description", "")[:100],
                "manufacturer": p.get("Final_Manufacturer"),
                "price": p.get("Price"),
                "micron": p.get("Micron_Rating"),
                "stock": p.get("Total_Stock", 0)
            })
        
        response = self.client.chat.completions.create(
            model=self.FAST_MODEL,
            messages=[{
                "role": "system",
                "content": """Pick the 3 best products for this sales rep's query. Consider:
- Application fit (does it match their use case?)
- Stock availability (prioritize in-stock items)
- Common sales patterns (what reps usually recommend)
- Price appropriateness

Return ONLY JSON: {"top_3": ["PN1", "PN2", "PN3"], "reasoning": "brief explanation"}"""
            }, {
                "role": "user",
                "content": f"Query: {query}\nFilters: {filters}\nProducts: {json.dumps(product_summary)}"
            }],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        top_3_pns = parsed.get("top_3", [])
        
        # Filter original list to top 3
        pn_set = set(top_3_pns)
        return [p for p in products if p.get("Part_Number") in pn_set][:3]
    
    async def _get_customer(self, customer_name: str) -> Dict:
        """Get customer context if available."""
        if self.customer_intel:
            return self.customer_intel.lookup(customer_name)
        return {"found": False}
    
    def _check_escalation(self, description: str) -> Dict:
        """Check for safety-critical terms."""
        dangerous = ["hydrogen", "h2s", "500f", "600f", "lethal", "chlorine", "steam 400"]
        if any(kw in description.lower() for kw in dangerous):
            return {
                "escalate": True,
                "reason": "Safety-critical application requires engineering review",
                "contact": "engineering@enpro.com"
            }
        return {"escalate": False}
    
    def _estimate_cost(self, usage) -> float:
        """Estimate cost in USD."""
        # o3-mini-high: ~$0.015 per request (approximate)
        return 0.015


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI ENDPOINT (Replace your existing /chat)
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

# Global instance (initialized in server.py)
mastermind: Optional[MastermindV3] = None

def init_mastermind(df: pd.DataFrame):
    """Initialize the mastermind with catalog data."""
    global mastermind
    mastermind = MastermindV3(df)
    logger.info("✅ Mastermind V3 initialized")


class ChatRequest(BaseModel):
    message: str
    session_id: str
    customer_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    products: List[Dict]
    follow_up: Optional[str]
    escalation: bool
    model_used: str
    cost: float


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Unified chat endpoint - replaces all previous routing logic.
    """
    if mastermind is None:
        return {"error": "Mastermind not initialized"}
    
    # Get conversation history
    from conversation_memory import read_history
    history = read_history(request.session_id)[-5:]  # Last 5 turns
    
    # Get customer context if available
    customer_context = None
    if request.customer_id:
        # Your existing customer_intel lookup
        pass
    
    # Call unified handler
    result = await mastermind.chat(
        message=request.message,
        history=history,
        customer_context=customer_context
    )
    
    # Save to history
    from conversation_memory import write_history
    write_history(request.session_id, "user", request.message)
    write_history(request.session_id, "assistant", result["response"])
    
    return ChatResponse(
        response=result["response"],
        products=result["products"],
        follow_up=result.get("follow_up"),
        escalation=result.get("escalation", False),
        model_used=result["model_used"],
        cost=result["cost"]
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY (Temporary)
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message_legacy(message: str, history: list = None, **kwargs):
    """
    Legacy compatibility wrapper.
    Drop-in replacement for router.handle_message()
    """
    if mastermind is None:
        raise RuntimeError("Mastermind not initialized")
    
    result = await mastermind.chat(message, history or [])
    
    # Format to match old response structure
    return {
        "intent": "unified",
        "response": result["response"],
        "products": result["products"],
        "to_user": result["response"],
        "follow_up": result.get("follow_up")
    }
