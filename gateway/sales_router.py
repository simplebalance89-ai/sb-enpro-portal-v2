"""
Sales-First Router
Routes requests to appropriate handlers based on business value.

Priority:
1. Pregame (strategic reasoning) → o3-mini-high
2. Compare (reasoning-driven) → o3-mini
3. Voice Lookup (phonetic resolution) → GPT-5.4 Mini + Azure STT
4. Quote Extraction → GPT-5.4 Mini
5. Chemical → Hardcoded lookup (zero cost)
6. Simple lookups → Pandas (zero cost)
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from models import (
    ModelRouter, ModelTier, get_model_router,
    ReasoningEngine, IntentClassifier, 
    get_chemical_expert, get_voice_resolver
)
from config import settings

logger = logging.getLogger("enpro.gateway.sales")


@dataclass
class RoutedResponse:
    """Standard response from the sales router."""
    intent: str
    headline: str
    body: Optional[str]
    picks: List[Dict[str, Any]]
    follow_up: Optional[str]
    reasoning_trace: Optional[List[str]]
    model_used: str
    cost: float
    latency_ms: float
    safety_flag: Optional[str] = None


class SalesFirstRouter:
    """
    Sales-first intent router.
    
    Replaces the monolithic router.py with modular, cost-optimized routing.
    """
    
    def __init__(self):
        self.model_router = get_model_router()
        self.reasoning = ReasoningEngine()
        self.classifier = IntentClassifier()
        self.chemical_expert = get_chemical_expert()
        self.voice_resolver = get_voice_resolver()
        
        # Stats tracking
        self._request_count = 0
        self._total_cost = 0.0
    
    async def route(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        voice_audio: Optional[bytes] = None,
        history: Optional[List[Dict]] = None
    ) -> RoutedResponse:
        """
        Main routing entry point.
        
        Analyzes message and routes to the best handler based on:
        - Business value (pregame > lookup > general)
        - Cost optimization (pattern matching before AI)
        - Safety (escalation checks first)
        """
        import time
        start_time = time.time()
        context = context or {}
        
        # ═══════════════════════════════════════════════════════════════════
        # Step 1: Intent Classification (Phi-4 or pattern matching)
        # ═══════════════════════════════════════════════════════════════════
        classification = await self.classifier.classify(
            message=message,
            use_model=settings.USE_MODULAR_MODELS,
            conversation_history=history
        )
        intent = classification["intent"]
        intent_confidence = classification["confidence"]
        intent_cost = classification.get("cost", 0.0)
        
        logger.info(f"Classified intent: {intent} (confidence: {intent_confidence})")
        
        # ═══════════════════════════════════════════════════════════════════
        # Step 2: Route by Intent
        # ═══════════════════════════════════════════════════════════════════
        
        # Pregame / Application → Strategic reasoning
        if intent in ["pregame", "application"]:
            result = await self._handle_pregame(message, context)
        
        # Compare → Reasoning-driven comparison
        elif intent == "compare":
            result = await self._handle_compare(message, context, history)
        
        # Voice Lookup → Phonetic resolution
        elif intent == "lookup" and voice_audio:
            result = await self._handle_voice_lookup(voice_audio, message, context)
        
        # Chemical → Hardcoded lookup (zero AI cost)
        elif intent == "chemical":
            result = await self._handle_chemical(message, context)
        
        # Quote State → Entity extraction
        elif intent in ["quote_ready", "system_quote"]:
            result = await self._handle_quote(message, context)
        
        # Simple lookups → Fast response
        elif intent in ["lookup", "price", "manufacturer", "supplier"]:
            result = await self._handle_fast_lookup(message, intent, context)
        
        # General / Fallback
        else:
            result = await self._handle_general(message, intent, context)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Update stats
        self._request_count += 1
        self._total_cost += result.get("cost", 0.0) + intent_cost
        
        return RoutedResponse(
            intent=intent,
            headline=result.get("headline", ""),
            body=result.get("body"),
            picks=result.get("picks", []),
            follow_up=result.get("follow_up"),
            reasoning_trace=result.get("reasoning_trace"),
            model_used=result.get("model_used", "unknown"),
            cost=round(result.get("cost", 0.0) + intent_cost, 6),
            latency_ms=round(latency_ms, 2),
            safety_flag=result.get("safety_flag")
        )
    
    async def _handle_pregame(self, message: str, context: Dict) -> Dict:
        """
        Strategic pregame with o3-mini-high reasoning.
        
        Shows thinking_trace to reps for credibility.
        """
        industry = self._extract_industry(message)
        customer_context = context.get("customer", {})
        catalog_products = context.get("products", [])
        
        result = await self.reasoning.pregame_reasoning(
            customer_industry=industry,
            customer_context=customer_context,
            catalog_products=catalog_products
        )
        
        return {
            "headline": result.headline,
            "body": result.body,
            "picks": result.picks,
            "follow_up": result.follow_up,
            "reasoning_trace": result.thinking_trace,
            "model_used": result.model_used,
            "cost": result.cost,
            "safety_flag": "escalation" if any("hydrogen" in str(t).lower() or "h2s" in str(t).lower() for t in result.thinking_trace) else None
        }
    
    async def _handle_compare(self, message: str, context: Dict, history: List) -> Dict:
        """
        Reasoning-driven comparison with o3-mini.
        """
        # Extract part numbers from message and history
        part_numbers = self._extract_part_numbers(message, history)
        
        if len(part_numbers) < 2:
            return {
                "headline": "Compare what parts?",
                "body": "I need at least 2 part numbers to compare. Try: 'compare HC9600 and CLR130'",
                "picks": [],
                "follow_up": "What parts would you like to compare?",
                "reasoning_trace": [],
                "model_used": "none",
                "cost": 0.0
            }
        
        # Get product details from catalog
        products = []
        for pn in part_numbers[:4]:  # Max 4 products
            product = context.get("catalog", {}).get(pn.upper())
            if product:
                products.append(product)
        
        if len(products) < 2:
            return {
                "headline": "Parts not found",
                "body": f"Could only find {len(products)} of the requested parts in catalog.",
                "picks": products,
                "follow_up": "Can you verify the part numbers?",
                "reasoning_trace": [],
                "model_used": "none",
                "cost": 0.0
            }
        
        result = await self.reasoning.compare_reasoning(
            part_numbers=part_numbers,
            products=products,
            context=context.get("customer_industry")
        )
        
        return {
            "headline": result.headline,
            "body": result.body,
            "picks": result.picks,
            "follow_up": result.follow_up,
            "reasoning_trace": result.thinking_trace,
            "model_used": result.model_used,
            "cost": result.cost
        }
    
    async def _handle_voice_lookup(self, audio: bytes, text_hint: str, context: Dict) -> Dict:
        """
        Voice part resolution with Azure STT + GPT-5.4 Mini.
        """
        # This would integrate with Azure Speech Services
        # For now, use the text hint with phonetic resolution
        
        resolution = await self.voice_resolver.resolve(
            transcription=text_hint,
            context={
                "recent_parts": context.get("recent_parts", []),
                "industry": context.get("industry")
            }
        )
        
        if resolution.resolved and resolution.confidence > 0.7:
            # Look up the resolved part
            product = context.get("catalog", {}).get(resolution.resolved)
            if product:
                return {
                    "headline": f"{resolution.resolved} — {product.get('Description', 'Part found')}",
                    "body": f"Heard: '{resolution.heard}'\nResolved: {resolution.resolved}",
                    "picks": [product],
                    "follow_up": "Is this the right part?",
                    "reasoning_trace": [f"Phonetic match confidence: {resolution.confidence:.0%}"],
                    "model_used": resolution.model_used,
                    "cost": resolution.cost
                }
        
        return {
            "headline": "Part not recognized",
            "body": f"Heard: '{resolution.heard}'\nCould not resolve to a valid part number.",
            "picks": [],
            "follow_up": "Can you spell out the part number?",
            "reasoning_trace": [f"Phonetic match confidence: {resolution.confidence:.0%}"],
            "model_used": resolution.model_used,
            "cost": resolution.cost
        }
    
    async def _handle_chemical(self, message: str, context: Dict) -> Dict:
        """
        Hardcoded chemical lookup - zero AI cost.
        """
        # Extract chemical name from message
        chemical = self._extract_chemical(message)
        concentration = self._extract_concentration(message)
        
        result = self.chemical_expert.lookup(chemical, concentration)
        
        # Format ratings into readable body
        if result["ratings"]:
            ratings_lines = []
            for material, rating_info in result["ratings"].items():
                ratings_lines.append(f"• {material}: {rating_info['rating']} — {rating_info['reasoning']}")
            body = "\n".join(ratings_lines)
        else:
            body = result.get("escalation_reason", "No ratings available")
        
        return {
            "headline": result["headline"],
            "body": body,
            "picks": [],
            "follow_up": "Need a specific seal recommendation?" if not result["escalate"] else None,
            "reasoning_trace": ["Hardcoded lookup — no AI reasoning"],
            "model_used": "hardcoded",
            "cost": 0.0,
            "safety_flag": "chemical_escalation" if result["escalate"] else None
        }
    
    async def _handle_quote(self, message: str, context: Dict) -> Dict:
        """
        Quote entity extraction with GPT-5.4 Mini.
        """
        current_quote = context.get("current_quote")
        
        entities = await self.reasoning.extract_quote_entities(message, current_quote)
        
        # Build response
        if entities.get("customer"):
            headline = f"Quote for {entities['customer']}"
        else:
            headline = "Building quote..."
        
        lines = []
        for item in entities.get("line_items", []):
            lines.append(f"• {item.get('quantity', 1)}x {item.get('part_number', 'Unknown')}")
        
        body = "\n".join(lines) if lines else "No items yet"
        
        if entities.get("missing_info"):
            body += f"\n\nStill need: {', '.join(entities['missing_info'])}"
        
        return {
            "headline": headline,
            "body": body,
            "picks": entities.get("line_items", []),
            "follow_up": "Add more items or ready to finalize?",
            "reasoning_trace": [f"Entity extraction confidence: {entities.get('confidence', 0)}"],
            "model_used": "gpt-5.4-mini",
            "cost": 0.003
        }
    
    async def _handle_fast_lookup(self, message: str, intent: str, context: Dict) -> Dict:
        """
        Fast lookup with GPT-5.4 Mini or Pandas.
        """
        # This would integrate with the existing search module
        # For now, return a placeholder
        return {
            "headline": f"Lookup: {message}",
            "body": "Using fast lookup...",
            "picks": [],
            "follow_up": None,
            "reasoning_trace": [],
            "model_used": "pandas/fast",
            "cost": 0.0
        }
    
    async def _handle_general(self, message: str, intent: str, context: Dict) -> Dict:
        """
        General response with GPT-5.4 Standard.
        """
        response = await self.model_router.complete(
            messages=[
                {"role": "system", "content": "You are the Enpro Filtration Mastermind. Answer filtration questions accurately and concisely."},
                {"role": "user", "content": message}
            ],
            tier=ModelTier.STANDARD
        )
        
        return {
            "headline": "Enpro Filtration",
            "body": response.content,
            "picks": [],
            "follow_up": "Anything else I can help with?",
            "reasoning_trace": [],
            "model_used": response.model_used,
            "cost": response.cost_estimate or 0.01
        }
    
    # ═══════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════
    
    def _extract_industry(self, message: str) -> str:
        """Extract industry from message."""
        industries = [
            "brewery", "winery", "distillery", "pharma", "pharmaceutical",
            "paint", "coating", "hydraulic", "mining", "pulp", "paper",
            "steel", "automotive", "aerospace", "data center", "semiconductor",
            "solar", "oil", "gas", "chemical", "food", "beverage"
        ]
        message_lower = message.lower()
        for industry in industries:
            if industry in message_lower:
                return industry
        return "general"
    
    def _extract_part_numbers(self, message: str, history: List) -> List[str]:
        """Extract part numbers from message and history."""
        import re
        pattern = r'\b([A-Z]{1,5}\d[\w\-/]{2,20})\b'
        found = set()
        
        # From current message
        for match in re.finditer(pattern, message, re.IGNORECASE):
            found.add(match.group(1).upper())
        
        # From history (recent turns)
        for msg in history[-4:] if history else []:
            content = msg.get("content", "")
            for match in re.finditer(pattern, content, re.IGNORECASE):
                found.add(match.group(1).upper())
        
        return list(found)
    
    def _extract_chemical(self, message: str) -> str:
        """Extract chemical name from message."""
        message_lower = message.lower()
        
        # Common chemicals
        chemicals = [
            "sulfuric acid", "hydrochloric acid", "nitric acid", "phosphoric acid",
            "sodium hydroxide", "potassium hydroxide", "ammonia",
            "acetone", "mek", "methyl ethyl ketone", "toluene", "xylene",
            "ethylene glycol", "propylene glycol", "glycerin",
            "hydraulic oil", "motor oil", "diesel", "gasoline",
            "hydrocarbon", "solvent"
        ]
        
        for chem in chemicals:
            if chem in message_lower:
                return chem
        
        # Try to extract after "chemical" or "compatibility"
        match = re.search(r'(?:chemical|compatibility|compatible with)\s+(?:of\s+)?([a-z\s]+?)(?:\s+at|\s+with|\?|$)', message_lower)
        if match:
            return match.group(1).strip()
        
        return "unknown"
    
    def _extract_concentration(self, message: str) -> Optional[str]:
        """Extract concentration from message."""
        import re
        match = re.search(r'(\d+)%|\b(concentrated|dilute|weak|strong)\b', message.lower())
        if match:
            return match.group(0)
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "requests": self._request_count,
            "total_cost_usd": round(self._total_cost, 4),
            "model_stats": self.model_router.get_stats(),
            "classifier_stats": self.classifier.get_stats()
        }


# Global instance
_sales_router: Optional[SalesFirstRouter] = None


def get_sales_router() -> SalesFirstRouter:
    """Get the global sales router instance."""
    global _sales_router
    if _sales_router is None:
        _sales_router = SalesFirstRouter()
    return _sales_router
