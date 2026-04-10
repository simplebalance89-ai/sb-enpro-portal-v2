"""
Enpro Filtration Mastermind v3.1 - With Phi-4 Classification
Cost-optimized: Phi-4 classifies, o3-mini reasons only when needed
"""

import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.openai import AzureOpenAI

logger = logging.getLogger("enpro.mastermind_v3")

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL DEPLOYMENTS - UPDATE THESE WITH YOUR AZURE AI FOUNDRY NAMES
# ═══════════════════════════════════════════════════════════════════════════════

# TODO: Replace with your actual Azure deployment names
PHI4_DEPLOYMENT = "phi-4"           # For classification (~$0.0001/query)
PHI4_FAST_DEPLOYMENT = "phi-4-mini" # For simple responses (~$0.0001/query)
O3_MINI_DEPLOYMENT = "o3-mini"      # For complex reasoning (~$0.015/query)
O3_MINI_HIGH_DEPLOYMENT = "o3-mini-high"  # For deep reasoning (~$0.015/query)
GPT54_MINI_DEPLOYMENT = "gpt-5.4-mini"    # For fast narrowing (~$0.003/query)

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

PHI4_CLASSIFIER_PROMPT = """You are a query classifier for Enpro Filtration.

Classify the user query into ONE category:

1. SIMPLE_LOOKUP - Part number lookup (e.g., "HC9600", "price of CLR130")
2. APPLICATION_HELP - Application guidance (e.g., "brewery filtration", "hydraulic system")
3. PREGAME - Meeting prep (e.g., "meeting with customer", "prep for brewery")
4. COMPARE - Product comparison (e.g., "compare HC9600 and CLR130")
5. GENERAL_CHAT - General question (e.g., "what's the difference", "how do I")
6. VOICE_TRANSCRIPTION - Voice input that needs phonetic resolution

Respond with ONLY the category name. One word.

Examples:
- "HC9600 price" → SIMPLE_LOOKUP
- "brewery yeast filtration" → APPLICATION_HELP
- "meeting with Acme Corp tomorrow" → PREGAME
- "compare HC9600 vs CLR130" → COMPARE
- "what's the difference between nominal and absolute" → GENERAL_CHAT
"""

O3_MINI_REASONING_PROMPT = """You are the Enpro Filtration Mastermind. A sales rep is texting you.

CRITICAL RULES:
1. NEVER say "400 products found" — narrow to 2-3 with reasoning
2. NEVER use command language — just answer naturally
3. ALWAYS ask ONE clarifying question if ambiguous
4. CARRY context from previous messages
5. GIVE reasoning: "I recommend X because Y"

RESPONSE FORMAT (JSON):
{
  "response_type": "recommendation|briefing|conversation|escalation",
  "to_user": "Natural conversational text, scannable on mobile",
  "headline": "ONE LINE verdict",
  "picks": [
    {
      "part_number": "EXACT_PN",
      "rank": 1,
      "reason": "ONE sentence why this fits",
      "specs": "$52, 12 in stock, MERV 13"
    }
  ],
  "follow_up_question": "ONE question or null",
  "context_update": {"industry": "brewery", "topic": "filter_life"},
  "escalation": false
}
"""

@dataclass
class ClassificationResult:
    category: str
    confidence: float
    needs_reasoning: bool
    needs_products: bool

class MastermindV3:
    """
    Cost-optimized unified handler with Phi-4 classification.
    
    Flow:
    1. Phi-4 classifies query (~$0.0001)
    2. Route to appropriate model:
       - Simple: Phi-4-mini response (~$0.0001)
       - Needs reasoning: o3-mini (~$0.015)
    3. If products needed: Search → Narrow with GPT-5.4-mini (~$0.003)
    """
    
    def __init__(self, catalog_df: pd.DataFrame):
        self.catalog_df = catalog_df
        
        self.client = AzureOpenAI(
            azure_endpoint="https://enpro-filtration-ai.services.ai.azure.com/",
            api_version="2024-12-01-preview",
            credential=DefaultAzureCredential()
        )
    
    async def chat(self, message: str, history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point with Phi-4 classification.
        """
        history = history or []
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Phi-4 Classification (Cheap: ~$0.0001)
        # ═══════════════════════════════════════════════════════════════════
        classification = await self._classify_with_phi4(message)
        logger.info(f"Phi-4 classified: {classification.category} (confidence: {classification.confidence})")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Route based on classification
        # ═══════════════════════════════════════════════════════════════════
        
        # Simple lookups - use Phi-4-mini (cheapest)
        if classification.category == "SIMPLE_LOOKUP":
            return await self._handle_simple_lookup(message, history)
        
        # General chat - use Phi-4-mini
        elif classification.category == "GENERAL_CHAT":
            return await self._handle_general_chat(message, history)
        
        # Complex queries - use o3-mini for reasoning
        elif classification.category in ["APPLICATION_HELP", "PREGAME", "COMPARE"]:
            return await self._handle_complex_query(message, history, classification)
        
        # Default to o3-mini
        else:
            return await self._handle_complex_query(message, history, classification)
    
    async def _classify_with_phi4(self, message: str) -> ClassificationResult:
        """
        Phi-4 classifies the query. 
        Cost: ~$0.0001 (vs $0.015 for o3-mini = 99% cheaper)
        """
        try:
            response = self.client.chat.completions.create(
                model=PHI4_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": PHI4_CLASSIFIER_PROMPT},
                    {"role": "user", "content": message}
                ],
                temperature=0.0,
                max_tokens=20
            )
            
            category = response.choices[0].message.content.strip().upper()
            
            # Map to standard categories
            category_map = {
                "SIMPLE_LOOKUP": "SIMPLE_LOOKUP",
                "APPLICATION_HELP": "APPLICATION_HELP",
                "APP_HELP": "APPLICATION_HELP",
                "PREGAME": "PREGAME",
                "PRE_GAME": "PREGAME",
                "COMPARE": "COMPARE",
                "COMPARISON": "COMPARE",
                "GENERAL_CHAT": "GENERAL_CHAT",
                "GENERAL": "GENERAL_CHAT",
                "VOICE_TRANSCRIPTION": "VOICE_TRANSCRIPTION",
            }
            
            mapped_category = category_map.get(category, "COMPLEX")
            
            # Determine routing
            needs_reasoning = mapped_category in ["APPLICATION_HELP", "PREGAME", "COMPARE", "COMPLEX"]
            needs_products = mapped_category in ["SIMPLE_LOOKUP", "APPLICATION_HELP", "COMPARE"]
            
            return ClassificationResult(
                category=mapped_category,
                confidence=0.9,  # Phi-4 is good at classification
                needs_reasoning=needs_reasoning,
                needs_products=needs_products
            )
            
        except Exception as e:
            logger.error(f"Phi-4 classification failed: {e}")
            # Fallback to complex query
            return ClassificationResult(
                category="COMPLEX",
                confidence=0.5,
                needs_reasoning=True,
                needs_products=True
            )
    
    async def _handle_simple_lookup(self, message: str, history: List[Dict]) -> Dict:
        """
        Simple part lookup - use Phi-4-mini (cheap & fast).
        """
        # Extract part number
        import re
        part_match = re.search(r'\b([A-Z]{2,4}\d{2,4})\b', message.upper())
        
        if part_match:
            part_number = part_match.group(1)
            # Search catalog
            product = self.catalog_df[self.catalog_df['Part_Number'] == part_number]
            
            if not product.empty:
                row = product.iloc[0]
                return {
                    "response_type": "recommendation",
                    "to_user": f"{row['Part_Number']} - {row['Description']}. Price: ${row.get('Price', 'N/A')}, Stock: {row.get('Total_Stock', 0)} units.",
                    "headline": f"{row['Part_Number']} - {row['Final_Manufacturer']}",
                    "picks": [{
                        "part_number": row['Part_Number'],
                        "rank": 1,
                        "reason": row['Description'],
                        "specs": f"${row.get('Price', 0)}, {row.get('Total_Stock', 0)} in stock"
                    }],
                    "follow_up_question": "Need pricing on a specific quantity?",
                    "model_used": PHI4_FAST_DEPLOYMENT,
                    "cost": 0.0001
                }
        
        # Fallback to o3-mini if Phi-4 can't handle it
        return await self._handle_complex_query(message, history, ClassificationResult("COMPLEX", 0.5, True, True))
    
    async def _handle_general_chat(self, message: str, history: List[Dict]) -> Dict:
        """
        General questions - use Phi-4-mini.
        """
        response = self.client.chat.completions.create(
            model=PHI4_FAST_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are Enpro's filtration expert. Answer briefly and helpfully."},
                {"role": "user", "content": message}
            ],
            max_tokens=200
        )
        
        return {
            "response_type": "conversation",
            "to_user": response.choices[0].message.content,
            "headline": None,
            "picks": [],
            "follow_up_question": None,
            "model_used": PHI4_FAST_DEPLOYMENT,
            "cost": 0.0001
        }
    
    async def _handle_complex_query(self, message: str, history: List[Dict], classification: ClassificationResult) -> Dict:
        """
        Complex queries - use o3-mini for reasoning.
        """
        # Search products if needed
        products = []
        if classification.needs_products:
            products = await self._search_products(message)
            if len(products) > 5:
                products = await self._narrow_to_three(message, products)
        
        # Generate with o3-mini
        history_text = self._format_history(history)
        products_text = json.dumps(products[:3], indent=2) if products else "No products needed"
        
        response = self.client.chat.completions.create(
            model=O3_MINI_HIGH_DEPLOYMENT,
            messages=[
                {"role": "system", "content": O3_MINI_REASONING_PROMPT},
                {"role": "user", "content": f"History: {history_text}\n\nProducts: {products_text}\n\nQuery: {message}"}
            ],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        parsed["model_used"] = O3_MINI_HIGH_DEPLOYMENT
        parsed["cost"] = 0.015
        
        return parsed
    
    async def _search_products(self, query: str) -> List[Dict]:
        """Search catalog (pandas for now, Azure Search later)."""
        # Simple search - can be improved
        results = []
        query_upper = query.upper()
        
        # Check part numbers
        for _, row in self.catalog_df.iterrows():
            if query_upper in str(row.get('Part_Number', '')).upper():
                results.append(self._product_to_dict(row))
            elif query_upper in str(row.get('Description', '')).upper():
                results.append(self._product_to_dict(row))
        
        return results[:20]
    
    async def _narrow_to_three(self, message: str, products: List[Dict]) -> List[Dict]:
        """Use GPT-5.4-mini to pick top 3."""
        # Simplified - just take first 3 for now
        # TODO: Implement proper narrowing with GPT-5.4-mini
        return products[:3]
    
    def _product_to_dict(self, row) -> Dict:
        return {
            "part_number": row.get('Part_Number'),
            "description": row.get('Description'),
            "manufacturer": row.get('Final_Manufacturer'),
            "price": row.get('Price'),
            "stock": row.get('Total_Stock')
        }
    
    def _format_history(self, history: List[Dict]) -> str:
        formatted = []
        for turn in history[-3:]:  # Last 3 turns
            role = "User" if turn.get("role") == "user" else "Assistant"
            formatted.append(f"{role}: {turn.get('content', '')[:100]}")
        return "\n".join(formatted)


# FastAPI endpoints
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v3")

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response_type: str
    to_user: str
    headline: Optional[str]
    picks: List[Dict]
    follow_up_question: Optional[str]
    model_used: str
    cost: float

# Global instance
mastermind: Optional[MastermindV3] = None

def init_mastermind(df: pd.DataFrame):
    global mastermind
    mastermind = MastermindV3(df)
    logger.info("✅ Mastermind V3.1 (with Phi-4) initialized")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if mastermind is None:
        raise HTTPException(status_code=500, detail="Mastermind not initialized")
    
    result = await mastermind.chat(
        message=request.message,
        history=[]  # TODO: Load from session
    )
    
    return ChatResponse(
        response_type=result.get("response_type", "conversation"),
        to_user=result["to_user"],
        headline=result.get("headline"),
        picks=result.get("picks", []),
        follow_up_question=result.get("follow_up_question"),
        model_used=result.get("model_used", "unknown"),
        cost=result.get("cost", 0.0)
    )
