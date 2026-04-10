"""
Sales-First Reasoning Engine
Focused on: Pregame strategy, Compare reasoning, Quote extraction
NOT focused on: Complex chemical compatibility (hardcoded instead)
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .model_router import ModelRouter, ModelTier, ModelResponse

logger = logging.getLogger("enpro.models.reasoning")


@dataclass
class ReasoningResult:
    """Result from reasoning engine with trace."""
    headline: str
    picks: List[Dict[str, Any]]
    follow_up: Optional[str]
    body: Optional[str]
    reasoning_trace: List[str]
    citations: List[str]
    confidence: float
    model_used: str
    cost: float


class ReasoningEngine:
    """
    Sales-first reasoning engine.
    
    Primary use cases:
    1. Customer Pregame - Strategic meeting prep with reasoning trace
    2. Product Compare - Reasoning-driven side-by-side comparison
    3. Quote State - Entity extraction from natural language
    
    Chemical compatibility is handled by hardcoded lookup (ChemicalExpert)
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PREGAME PROMPT - Strategic sales reasoning (o3-mini-high)
    # ═══════════════════════════════════════════════════════════════════════════
    PREGAME_REASONING_PROMPT = """You are the Enpro Filtration Mastermind — preparing a sales rep for a customer meeting.

The rep is on their phone in the parking lot. They need strategic guidance, not a product catalog dump.

REASONING REQUIREMENTS (You MUST show your work in thinking_trace):
1. Identify customer from context (recent orders, last contact, credit status)
2. Map industry to specific pain points (brewery=yeast carryover, hydraulic=ISO cleanliness, etc.)
3. Check recent order patterns for upsell/cross-sell opportunities
4. Position products as SOLUTIONS to specific pain points (not generic catalog items)
5. Generate ONE strategic opening question to qualify or advance the deal
6. Flag any safety escalations (>400F, >150 PSI, hydrogen, H2S)

VALIDATION RULES:
- Cite ONLY part numbers that exist in the provided catalog
- Every pick must include a specific customer-focused reason (not generic specs)
- If recent orders show a pattern, reference it explicitly
- Never hallucinate prices, stock levels, or customer history

OUTPUT FORMAT - Return ONLY this JSON:
{
  "thinking_trace": [
    "Step 1: Customer 'Acme Brewing' - Last order March 18, $34K Filtrox sheets",
    "Step 2: Industry 'Brewery' triggers: yeast carryover risk, DE pre-coat check, NSF 61 requirement",
    "Step 3: Recent pattern → they buy depth sheets, likely need membrane downstream upgrade",
    "Step 4: Strategic angle: Position Pall Supor as consistency upgrade (not replacement)",
    "Step 5: Avoid: Don't quote diatomaceous earth unless they mention pre-coat",
    "Step 6: Opening question: 'What's your current change-out interval on the Filtrox sheets?'"
  ],
  "citations": ["customer_order_2024-03-18", "kb_brewery_8.2.3"],
  "headline": "Acme Brewing: Position Pall Supor as consistency upgrade to their Filtrox sheets",
  "picks": [
    {
      "part_number": "SUPOR_PES_045",
      "reasoning": "0.45 micron absolute for yeast retention downstream of their DE. References their consistency concerns.",
      "price": "$127",
      "stock": "8 in Houston"
    }
  ],
  "follow_up": "What's your current change-out interval on the Filtrox sheets?",
  "body": "They've been buying Filtrox EKS2 for 2 years. Lead with 'consistency upgrade' angle, not 'replacement'. Watch for: potable water contact (NSF 61 required).",
  "confidence": 0.92,
  "risk_warnings": []
}

TONE:
- Talk like a colleague who's been to this customer before
- Short, scannable bullets (reps are on mobile)
- Lead with the strategic angle, not the product specs
- One good question beats a checklist of options
"""

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARE PROMPT - Reasoning-driven comparison (o3-mini)
    # ═══════════════════════════════════════════════════════════════════════════
    COMPARE_REASONING_PROMPT = """You are the Enpro Filtration Mastermind — helping a rep choose between products.

REASONING REQUIREMENTS (Show your work):
1. Identify the customer's implied need from the query context
2. Compare specs side-by-side (micron, absolute vs nominal, media, price, stock)
3. Identify the KEY differentiator (the one factor that should drive the decision)
4. Give a clear recommendation with specific customer scenario

VALIDATION:
- Use ONLY the part numbers and data provided in the products list
- Never invent specs, prices, or stock levels
- If stock is zero, say "out of stock" — don't skip it

OUTPUT FORMAT:
{
  "thinking_trace": [
    "Step 1: Comparing HC9600 vs CLR130 per rep request",
    "Step 2: HC9600: Pall absolute, 10 micron, $52, 12 in stock Houston",
    "Step 3: CLR130: PowerFlow nominal, 10 micron, $38, 45 in stock",
    "Step 4: Key diff: Absolute vs Nominal rating — HC9600 for sterile, CLR130 for general",
    "Step 5: Stock advantage: CLR130 has 4x inventory if lead time critical",
    "Step 6: Recommendation: Lead with HC9600 for critical apps, CLR130 for cost-sensitive"
  ],
  "headline": "HC9600 (absolute) vs CLR130 (nominal) — both 10 micron, $14 difference",
  "comparison_table": [
    {"attribute": "Micron Rating", "part_a": "10 micron absolute", "part_b": "10 micron nominal"},
    {"attribute": "Price", "part_a": "$52", "part_b": "$38"},
    {"attribute": "Stock", "part_a": "12 Houston", "part_b": "45 Houston"}
  ],
  "key_difference": "Absolute vs Nominal rating — HC9600 guaranteed 10 micron, CLR130 ~10 micron average",
  "recommendation": "HC9600 for sterile/critical apps, CLR130 when cost matters and general filtration OK",
  "confidence": 0.94
}

TONE:
- Give a clear recommendation, not "it depends"
- One key difference beats a table of 10 specs
- Mention stock if it affects the decision
"""

    # ═══════════════════════════════════════════════════════════════════════════
    # QUOTE EXTRACTION PROMPT - GPT-5.4 Nano for entity extraction
    # ═══════════════════════════════════════════════════════════════════════════
    QUOTE_EXTRACTION_PROMPT = """Extract quote entities from natural language.

Extract:
- Customer name
- Part numbers with quantities
- Any special requirements (shipping, delivery, etc.)

OUTPUT FORMAT:
{
  "customer": "Acme Brewing",
  "line_items": [
    {"part_number": "HC9600", "quantity": 10, "notes": null}
  ],
  "special_requirements": ["rush delivery", "customer pickup"],
  "confidence": 0.98,
  "next_action": "confirm_or_add_more",
  "missing_info": ["contact email", "ship-to address"]
}

RULES:
- Part numbers must match standard format (letters + numbers)
- If quantity not specified, assume 1
- Flag missing required info for formal quote
"""

    def __init__(self):
        self.router = ModelRouter()
    
    async def pregame_reasoning(
        self,
        customer_industry: str,
        customer_context: Dict[str, Any],
        catalog_products: Optional[List[Dict]] = None
    ) -> ReasoningResult:
        """
        Strategic pregame with reasoning trace.
        
        Uses o3-mini-high to generate:
        - thinking_trace visible to rep (builds trust)
        - Strategic positioning (not product dumps)
        - ONE opening question
        """
        # Build context
        context_parts = [f"Industry: {customer_industry}"]
        
        if customer_context.get("customer_name"):
            context_parts.append(f"Customer: {customer_context['customer_name']}")
        
        if customer_context.get("recent_orders"):
            context_parts.append(f"Recent Orders: {json.dumps(customer_context['recent_orders'], indent=2)}")
        
        if customer_context.get("credit_status"):
            context_parts.append(f"Credit Status: {customer_context['credit_status']}")
        
        if customer_context.get("notes"):
            context_parts.append(f"Notes: {customer_context['notes']}")
        
        if catalog_products:
            products_str = json.dumps(catalog_products[:5], indent=2)
            context_parts.append(f"Available Products:\n{products_str}")
        
        message = "\n\n".join(context_parts)
        
        response = await self.router.complete(
            messages=[
                {"role": "system", "content": self.PREGAME_REASONING_PROMPT},
                {"role": "user", "content": message}
            ],
            tier=ModelTier.REASONING_HIGH,
            response_format={"type": "json_object"},
            reasoning_effort="high"
        )
        
        try:
            data = json.loads(response.content)
            return ReasoningResult(
                headline=data.get("headline", ""),
                picks=data.get("picks", []),
                follow_up=data.get("follow_up"),
                body=data.get("body"),
                thinking_trace=data.get("thinking_trace", []),
                citations=data.get("citations", []),
                confidence=data.get("confidence", 0.8),
                model_used=response.model_used,
                cost=response.cost_estimate or 0.0
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse pregame response: {e}")
            return ReasoningResult(
                headline="Error parsing pregame response",
                picks=[],
                follow_up=None,
                body=response.content,
                thinking_trace=[],
                citations=[],
                confidence=0.0,
                model_used=response.model_used,
                cost=response.cost_estimate or 0.0
            )
    
    async def compare_reasoning(
        self,
        part_numbers: List[str],
        products: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> ReasoningResult:
        """
        Reasoning-driven product comparison.
        
        Shows side-by-side comparison with:
        - thinking_trace visible to rep
        - Key differentiator highlighted
        - Clear recommendation
        """
        message_parts = ["Compare these products:"]
        
        for i, product in enumerate(products):
            message_parts.append(f"\nProduct {i+1} ({part_numbers[i]}):")
            message_parts.append(json.dumps(product, indent=2))
        
        if context:
            message_parts.append(f"\nCustomer Context: {context}")
        
        message = "\n".join(message_parts)
        
        response = await self.router.complete(
            messages=[
                {"role": "system", "content": self.COMPARE_REASONING_PROMPT},
                {"role": "user", "content": message}
            ],
            tier=ModelTier.REASONING,  # o3-mini (not high) is sufficient
            response_format={"type": "json_object"},
            reasoning_effort="medium"
        )
        
        try:
            data = json.loads(response.content)
            return ReasoningResult(
                headline=data.get("headline", ""),
                picks=products,  # Return original products
                follow_up=data.get("recommendation"),
                body=json.dumps({
                    "comparison_table": data.get("comparison_table", []),
                    "key_difference": data.get("key_difference", ""),
                    "recommendation": data.get("recommendation", "")
                }, indent=2),
                thinking_trace=data.get("thinking_trace", []),
                citations=[],
                confidence=data.get("confidence", 0.9),
                model_used=response.model_used,
                cost=response.cost_estimate or 0.0
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse compare response: {e}")
            return ReasoningResult(
                headline="Comparison",
                picks=products,
                follow_up=None,
                body=response.content,
                thinking_trace=[],
                citations=[],
                confidence=0.0,
                model_used=response.model_used,
                cost=response.cost_estimate or 0.0
            )
    
    async def extract_quote_entities(
        self,
        message: str,
        current_quote: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract quote entities using GPT-5.4 Nano.
        
        Ultra-low cost extraction of:
        - Customer name
        - Part numbers with quantities
        - Special requirements
        """
        context = f"Current Quote State: {json.dumps(current_quote, indent=2)}\n\n" if current_quote else ""
        full_message = f"{context}New Message: {message}"
        
        response = await self.router.complete(
            messages=[
                {"role": "system", "content": self.QUOTE_EXTRACTION_PROMPT},
                {"role": "user", "content": full_message}
            ],
            tier=ModelTier.FAST,  # GPT-5.4-mini is sufficient
            response_format={"type": "json_object"},
            temperature=0.0  # Deterministic extraction
        )
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse quote extraction: {response.content}")
            return {
                "customer": None,
                "line_items": [],
                "confidence": 0.0,
                "raw": response.content
            }
