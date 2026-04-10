"""
Enpro Filtration Mastermind v3.0 PRODUCTION
Using your deployed Azure AI Foundry models

Model Mappings:
- phi-4-classifier → Classification (cheap, fast)
- gpt-4.1-mini → Fast/lightweight responses
- o4-mini-reasoning → Complex reasoning (replaces o3-mini)
- gpt-4.1 → Strong reasoning (replaces o3-mini-high)
- gpt-5-mini → Product narrowing (replaces gpt-5.4-mini)
"""

import json
import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import os
import pandas as pd
from azure.openai import AzureOpenAI
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("enpro.mastermind")

# ═══════════════════════════════════════════════════════════════════════════════
# YOUR AZURE AI FOUNDRY MODEL DEPLOYMENTS (from environment)
# ═══════════════════════════════════════════════════════════════════════════════

PHI4_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT_CLASSIFIER", "phi-4-classifier")
PHI4_FAST_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT_FAST", "gpt-4.1-mini")
O3_MINI_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT_REASONING", "o4-mini-reasoning")
O3_MINI_HIGH_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT_STRATEGIC", "gpt-4.1")
GPT54_MINI_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT_ROUTER", "gpt-5-mini")

# Azure endpoint configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://enpro-filtration-ai.services.ai.azure.com/api/projects/enpro-filtration-ai-project/openai/v1")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2026-01-01")

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

PHI4_CLASSIFIER_PROMPT = """You are a query classifier for Enpro Filtration.

Classify the user query into EXACTLY ONE category:

1. SIMPLE_LOOKUP - Part number lookup (e.g., "HC9600", "price of CLR130", "POM25 availability")
2. APPLICATION_HELP - Application guidance (e.g., "brewery filtration", "hydraulic system 10 micron")
3. PREGAME - Meeting prep (e.g., "meeting with customer tomorrow", "prep for brewery")
4. COMPARE - Product comparison (e.g., "compare HC9600 and CLR130", "vs", "difference between")
5. GENERAL_CHAT - General questions (e.g., "what's the difference", "how do I", "what is")
6. VOICE_TRANSCRIPTION - Voice input that needs phonetic resolution

Respond with ONLY the category name. One or two words maximum.

Examples:
- "HC9600 price" → SIMPLE_LOOKUP
- "brewery yeast filtration" → APPLICATION_HELP
- "meeting with Acme Corp tomorrow" → PREGAME
- "compare HC9600 vs CLR130" → COMPARE
- "what's the difference between nominal and absolute" → GENERAL_CHAT
- "aitch see ninety six oh oh" → VOICE_TRANSCRIPTION"""

O4_MINI_REASONING_PROMPT = """You are the Enpro Filtration Mastermind. A sales rep is texting you from their phone.

CRITICAL RULES (Never Break):
1. NEVER say "400 products found" — narrow to 2-3 specific recommendations with reasoning
2. NEVER use command language like "say lookup" — just answer naturally
3. ALWAYS ask ONE clarifying question if the request is ambiguous
4. CARRY context from previous messages — reference earlier topics naturally
5. GIVE reasoning: "I recommend X because Y" — reps need to explain to customers
6. MOBILE-FRIENDLY: Short paragraphs, scannable text, no wide tables

CONVERSATION STYLE:
- Lead with the verdict: "For data center HVAC, I'd start with..."
- Reference context: "Since you mentioned 10 micron earlier..."
- Sound like a colleague, not a search engine
- End with ONE question to move the deal forward

RESPONSE FORMAT (JSON only):
{
  "response_type": "recommendation|briefing|conversation|escalation",
  "to_user": "Natural conversational text, scannable on mobile, NO tables or bullet lists",
  "thinking_trace": ["Step 1: User asked...", "Step 2: Looking for..."],
  "headline": "ONE LINE verdict - lead with the answer",
  "picks": [
    {
      "part_number": "EXACT_PN_FROM_CATALOG",
      "rank": 1,
      "reason": "ONE sentence why this fits - price, stock, application match",
      "specs": "$52, 12 in stock Houston, MERV 13"
    }
  ],
  "follow_up_question": "ONE question to qualify or close, or null",
  "context_update": {"industry": "brewery", "customer": "Acme Corp", "topic": "filter_life"},
  "escalation": false,
  "escalation_reason": null
}

SAFETY ESCALATION (Set escalation: true if):
- Temperature > 400°F mentioned
- Hydrogen or H2S service
- Pressure > 150 PSI without context
- User mentions "lethal", "steam 400", "sour gas""""

@dataclass
class ClassificationResult:
    category: str
    confidence: float
    needs_reasoning: bool
    needs_products: bool


class EnproMastermindV3:
    """
    Production-ready unified handler with cost-optimized model routing.
    
    Model Routing Strategy:
    - Phi-4 (phi-4-classifier): Classification ~$0.0001
    - GPT-4.1-mini (gpt-4.1-mini): Simple lookups ~$0.002
    - O4-mini (o4-mini-reasoning): Complex reasoning ~$0.015
    - GPT-4.1 (gpt-4.1): Deep reasoning/briefings ~$0.02
    - GPT-5-mini (gpt-5-mini): Product narrowing ~$0.005
    """
    
    def __init__(self, catalog_df: pd.DataFrame):
        self.catalog_df = catalog_df
        
        # Use API key auth for Azure AI Foundry
        if not AZURE_API_KEY:
            raise ValueError("AZURE_OPENAI_KEY environment variable is required")
        
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT.rstrip('/'),
            api_version=AZURE_API_VERSION,
            api_key=AZURE_API_KEY
        )
        
        logger.info(f"✅ Mastermind initialized with models:")
        logger.info(f"   Classifier: {PHI4_DEPLOYMENT}")
        logger.info(f"   Fast: {PHI4_FAST_DEPLOYMENT}")
        logger.info(f"   Reasoning: {O3_MINI_DEPLOYMENT}")
        logger.info(f"   Deep: {O3_MINI_HIGH_DEPLOYMENT}")
        logger.info(f"   Narrow: {GPT54_MINI_DEPLOYMENT}")
    
    async def chat(self, message: str, history: List[Dict] = None) -> Dict[str, Any]:
        """
        Main entry point with intelligent model routing.
        """
        history = history or []
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: Phi-4 Classification (Cheap: ~$0.0001)
        # ═══════════════════════════════════════════════════════════════════
        classification = await self._classify_with_phi4(message)
        logger.info(f"📊 Phi-4 classified: {classification.category}")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: Route based on classification
        # ═══════════════════════════════════════════════════════════════════
        
        # Simple lookups → GPT-4.1-mini (cheap, fast)
        if classification.category == "SIMPLE_LOOKUP":
            return await self._handle_simple_lookup(message, history)
        
        # General chat → GPT-4.1-mini
        elif classification.category == "GENERAL_CHAT":
            return await self._handle_general_chat(message, history)
        
        # Voice transcription → Handle phonetically
        elif classification.category == "VOICE_TRANSCRIPTION":
            return await self._handle_voice_transcription(message, history)
        
        # Complex queries → O4-mini or GPT-4.1
        elif classification.category == "PREGAME":
            return await self._handle_pregame(message, history)
        
        elif classification.category in ["APPLICATION_HELP", "COMPARE"]:
            return await self._handle_complex_query(message, history, classification)
        
        # Default to complex
        else:
            return await self._handle_complex_query(message, history, classification)
    
    async def _classify_with_phi4(self, message: str) -> ClassificationResult:
        """
        Phi-4 (phi-4-classifier) determines routing.
        Cost: ~$0.0001 vs o4-mini ~$0.015 = 99% cheaper for classification
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
            
            # Normalize categories
            category_map = {
                "SIMPLE_LOOKUP": "SIMPLE_LOOKUP",
                "LOOKUP": "SIMPLE_LOOKUP",
                "APPLICATION_HELP": "APPLICATION_HELP",
                "APP_HELP": "APPLICATION_HELP",
                "PREGAME": "PREGAME",
                "PRE_GAME": "PREGAME",
                "MEETING_PREP": "PREGAME",
                "COMPARE": "COMPARE",
                "COMPARISON": "COMPARE",
                "VS": "COMPARE",
                "GENERAL_CHAT": "GENERAL_CHAT",
                "GENERAL": "GENERAL_CHAT",
                "VOICE_TRANSCRIPTION": "VOICE_TRANSCRIPTION",
                "VOICE": "VOICE_TRANSCRIPTION",
            }
            
            mapped_category = category_map.get(category, "COMPLEX")
            
            # Determine routing
            needs_reasoning = mapped_category in ["APPLICATION_HELP", "PREGAME", "COMPARE", "COMPLEX"]
            needs_products = mapped_category in ["SIMPLE_LOOKUP", "APPLICATION_HELP", "COMPARE", "VOICE_TRANSCRIPTION"]
            
            return ClassificationResult(
                category=mapped_category,
                confidence=0.9,
                needs_reasoning=needs_reasoning,
                needs_products=needs_products
            )
            
        except Exception as e:
            logger.error(f"❌ Phi-4 classification failed: {e}")
            # Safe fallback
            return ClassificationResult(
                category="COMPLEX",
                confidence=0.5,
                needs_reasoning=True,
                needs_products=True
            )
    
    async def _handle_simple_lookup(self, message: str, history: List[Dict]) -> Dict:
        """
        Simple part lookup → GPT-4.1-mini (fast, cheap).
        Cost: ~$0.002 vs O4-mini ~$0.015 = 87% savings
        """
        # Extract part number
        part_match = re.search(r'\b([A-Z]{2,5}\d{2,6}[A-Z]?)\b', message.upper())
        
        if part_match:
            part_number = part_match.group(1)
            
            # Search catalog
            product = self.catalog_df[self.catalog_df['Part_Number'] == part_number]
            
            if not product.empty:
                row = product.iloc[0]
                return {
                    "response_type": "recommendation",
                    "to_user": f"{row['Part_Number']} — {row['Description'][:80]}... Price: ${row.get('Price', 'N/A')}, Stock: {row.get('Total_Stock', 0)} units in Houston.",
                    "thinking_trace": ["Simple lookup", f"Found {part_number}"],
                    "headline": f"{row['Part_Number']} — {row['Final_Manufacturer']}",
                    "picks": [{
                        "part_number": row['Part_Number'],
                        "rank": 1,
                        "reason": row['Description'][:100],
                        "specs": f"${row.get('Price', 0)}, {row.get('Total_Stock', 0)} in stock"
                    }],
                    "follow_up_question": "Need pricing on a specific quantity?",
                    "context_update": {"last_part": row['Part_Number']},
                    "escalation": False,
                    "model_used": PHI4_FAST_DEPLOYMENT,
                    "cost": 0.002
                }
        
        # Fallback to complex if simple lookup fails
        return await self._handle_complex_query(
            message, history, 
            ClassificationResult("COMPLEX", 0.5, True, True)
        )
    
    async def _handle_general_chat(self, message: str, history: List[Dict]) -> Dict:
        """
        General questions → GPT-4.1-mini.
        Cost: ~$0.002
        """
        response = self.client.chat.completions.create(
            model=PHI4_FAST_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are Enpro's filtration expert. Answer briefly and helpfully. 2-3 sentences max."},
                {"role": "user", "content": message}
            ],
            max_tokens=150
        )
        
        return {
            "response_type": "conversation",
            "to_user": response.choices[0].message.content,
            "thinking_trace": ["General chat response"],
            "headline": None,
            "picks": [],
            "follow_up_question": None,
            "context_update": {},
            "escalation": False,
            "model_used": PHI4_FAST_DEPLOYMENT,
            "cost": 0.002
        }
    
    async def _handle_voice_transcription(self, message: str, history: List[Dict]) -> Dict:
        """
        Voice input that needs phonetic resolution.
        """
        # Use GPT-5-mini to resolve phonetics
        response = self.client.chat.completions.create(
            model=GPT54_MINI_DEPLOYMENT,
            messages=[{
                "role": "system",
                "content": "Resolve phonetic transcription to part number. Return JSON: {\"part_number\": \"HC9600\", \"confidence\": 0.95}"
            }, {
                "role": "user",
                "content": f"Transcription: '{message}'"
            }],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        resolved_part = parsed.get("part_number", "").upper()
        
        # Look up resolved part
        if resolved_part:
            product = self.catalog_df[self.catalog_df['Part_Number'] == resolved_part]
            if not product.empty:
                row = product.iloc[0]
                return {
                    "response_type": "recommendation",
                    "to_user": f"Heard '{message}' → {resolved_part}. {row['Description'][:60]}... Price: ${row.get('Price', 'N/A')}, Stock: {row.get('Total_Stock', 0)}.",
                    "thinking_trace": ["Voice transcription", f"Resolved to {resolved_part}"],
                    "headline": f"{resolved_part} — {row['Final_Manufacturer']}",
                    "picks": [{
                        "part_number": row['Part_Number'],
                        "rank": 1,
                        "reason": f"Phonetic match from '{message}'",
                        "specs": f"${row.get('Price', 0)}, {row.get('Total_Stock', 0)} in stock"
                    }],
                    "follow_up_question": "Is this the right part?",
                    "model_used": GPT54_MINI_DEPLOYMENT,
                    "cost": 0.005
                }
        
        # Couldn't resolve
        return {
            "response_type": "conversation",
            "to_user": f"Heard '{message}' but couldn't match to a part number. Can you spell it out?",
            "model_used": GPT54_MINI_DEPLOYMENT,
            "cost": 0.005
        }
    
    async def _handle_pregame(self, message: str, history: List[Dict]) -> Dict:
        """
        Meeting prep → GPT-4.1 (strong reasoning for strategic briefing).
        Cost: ~$0.02 (worth it for complex pregame)
        """
        history_text = self._format_history(history)
        
        response = self.client.chat.completions.create(
            model=O3_MINI_HIGH_DEPLOYMENT,
            messages=[{
                "role": "system",
                "content": O4_MINI_REASONING_PROMPT + "\n\nFor PREGAME: Create a strategic briefing the rep can read aloud. Include: Opening line, 2-3 product recommendations, ONE key question to ask, and what to avoid mentioning."
            }, {
                "role": "user",
                "content": f"History: {history_text}\n\nPregame request: {message}"
            }],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        parsed["response_type"] = "briefing"
        parsed["model_used"] = O3_MINI_HIGH_DEPLOYMENT
        parsed["cost"] = 0.02
        
        return parsed
    
    async def _handle_complex_query(self, message: str, history: List[Dict], 
                                   classification: ClassificationResult) -> Dict:
        """
        Complex queries → O4-mini with product search.
        Cost: ~$0.015 + $0.005 for narrowing = ~$0.02 total
        """
        # Search products if needed
        products = []
        if classification.needs_products:
            products = await self._search_products(message)
            if len(products) > 5:
                products = await self._narrow_with_gpt5(message, products)
        
        # Generate with O4-mini
        history_text = self._format_history(history)
        products_text = json.dumps(products[:3], indent=2) if products else "No matching products in catalog"
        
        response = self.client.chat.completions.create(
            model=O3_MINI_DEPLOYMENT,
            messages=[{
                "role": "system",
                "content": O4_MINI_REASONING_PROMPT
            }, {
                "role": "user",
                "content": f"History: {history_text}\n\nAvailable products: {products_text}\n\nQuery: {message}"
            }],
            response_format={"type": "json_object"}
        )
        
        parsed = json.loads(response.choices[0].message.content)
        
        # Attach full product data to picks
        for pick in parsed.get("picks", []):
            full_product = next((p for p in products if p["part_number"] == pick["part_number"]), None)
            if full_product:
                pick["stock"] = full_product.get("stock", {})
                pick["price"] = full_product.get("price")
        
        parsed["model_used"] = O3_MINI_DEPLOYMENT
        parsed["cost"] = 0.015 + (0.005 if len(products) > 5 else 0)
        
        return parsed
    
    async def _search_products(self, query: str) -> List[Dict]:
        """Search catalog with multiple strategies."""
        results = []
        query_upper = query.upper()
        
        # Strategy 1: Exact part number
        for _, row in self.catalog_df.iterrows():
            if query_upper == str(row.get('Part_Number', '')).upper():
                results.append(self._product_to_dict(row))
        
        # Strategy 2: Contains part number
        if not results:
            for _, row in self.catalog_df.iterrows():
                pn = str(row.get('Part_Number', '')).upper()
                if query_upper in pn or pn in query_upper:
                    results.append(self._product_to_dict(row))
        
        # Strategy 3: Description search
        if not results:
            for _, row in self.catalog_df.iterrows():
                desc = str(row.get('Description', '')).upper()
                if any(word in desc for word in query_upper.split()[:3]):
                    results.append(self._product_to_dict(row))
        
        # Sort by relevance (exact match first)
        return results[:20]
    
    async def _narrow_with_gpt5(self, message: str, products: List[Dict]) -> List[Dict]:
        """
        GPT-5-mini narrows 20 products to top 3.
        Cost: ~$0.005
        """
        candidates = products[:15]
        
        candidates_text = json.dumps([{
            "pn": p["part_number"],
            "desc": p["description"][:80],
            "price": p["price"],
            "stock": p["stock"]["total"] if isinstance(p["stock"], dict) else p["stock"]
        } for p in candidates])
        
        response = self.client.chat.completions.create(
            model=GPT54_MINI_DEPLOYMENT,
            messages=[{
                "role": "system",
                "content": "Select the 3 best products for this query. Consider: application fit, price, stock, relevance. Return JSON: {\"top_3\": [\"PN1\", \"PN2\", \"PN3\"]}"
            }, {
                "role": "user",
                "content": f"Query: {message}\nCandidates: {candidates_text}"
            }],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        result = json.loads(response.choices[0].message.content)
        top_pns = result.get("top_3", [])
        
        return [p for p in products if p["part_number"] in top_pns][:3]
    
    def _product_to_dict(self, row) -> Dict:
        """Convert DataFrame row to dict."""
        return {
            "part_number": row.get('Part_Number'),
            "description": row.get('Description'),
            "manufacturer": row.get('Final_Manufacturer'),
            "price": row.get('Price', 0),
            "stock": {
                "total": row.get('Total_Stock', 0),
                "houston": row.get('Qty_Loc_10', 0) + row.get('Qty_Loc_22', 0),
                "charlotte": row.get('Qty_Loc_12', 0),
                "kansas_city": row.get('Qty_Loc_30', 0)
            },
            "specs": {
                "micron": row.get('Micron_Rating'),
                "merv": row.get('MERV_Rating')
            }
        }
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format last 3 turns for context."""
        formatted = []
        for turn in history[-3:]:
            role = "User" if turn.get("role") == "user" else "Assistant"
            formatted.append(f"{role}: {turn.get('content', '')[:100]}")
        return "\n".join(formatted)


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/v3")

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response_type: str
    to_user: str
    thinking_trace: Optional[List[str]]
    headline: Optional[str]
    picks: List[Dict]
    follow_up_question: Optional[str]
    context_update: Dict
    escalation: bool
    model_used: str
    cost: float

# Global instance
mastermind: Optional[EnproMastermindV3] = None

def init_mastermind(df: pd.DataFrame):
    global mastermind
    mastermind = EnproMastermindV3(df)
    logger.info("✅ Production Mastermind initialized with Phi-4 + GPT-4.1 + O4-mini routing")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if mastermind is None:
        raise HTTPException(status_code=500, detail="Mastermind not initialized")
    
    result = await mastermind.chat(
        message=request.message,
        history=[]  # TODO: Load from session storage
    )
    
    return ChatResponse(
        response_type=result.get("response_type", "conversation"),
        to_user=result["to_user"],
        thinking_trace=result.get("thinking_trace"),
        headline=result.get("headline"),
        picks=result.get("picks", []),
        follow_up_question=result.get("follow_up_question"),
        context_update=result.get("context_update", {}),
        escalation=result.get("escalation", False),
        model_used=result.get("model_used", "unknown"),
        cost=result.get("cost", 0.0)
    )

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "3.0-prod",
        "models": {
            "classifier": PHI4_DEPLOYMENT,
            "fast": PHI4_FAST_DEPLOYMENT,
            "reasoning": O3_MINI_DEPLOYMENT,
            "deep": O3_MINI_HIGH_DEPLOYMENT,
            "narrow": GPT54_MINI_DEPLOYMENT
        }
    }
