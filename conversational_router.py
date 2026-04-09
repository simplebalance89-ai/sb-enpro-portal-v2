"""
Enpro Conversational Router v2.16

Replaces the 14-command router with a 5-category conversational model:
- SEARCH: Find products
- ADVICE: Get recommendations  
- CLARIFY: Ask follow-up questions
- QUOTE: Build quotes
- GREETING: Casual chat

This enables the "knowledgeable colleague" experience.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from azure_client import route_message, reason
from conversation_context import context_manager, ConversationContext
from system_prompts import get_prompt
from voice_gate import VoiceGate

logger = logging.getLogger("enpro.conversational_router")


@dataclass
class ConversationalResponse:
    """Structured response for conversational AI."""
    headline: str
    recommendations: List[Dict[str, Any]]
    follow_up: str
    context_update: Dict[str, Any]
    response_text: str  # Full formatted response
    intent: str
    cost: str = "$0"


class ConversationalRouter:
    """
    Routes natural language queries to appropriate handlers.
    No commands, just conversation.
    """
    
    def __init__(self, voice_gate: VoiceGate):
        self.voice_gate = voice_gate
        self.context_manager = context_manager
    
    async def handle_message(
        self, 
        message: str, 
        session_id: str,
        df=None,
        chemical_df=None
    ) -> Dict[str, Any]:
        """
        Main entry point for conversational handling.
        
        Flow:
        1. Get/create conversation context
        2. Classify intent (5 categories)
        3. Route to handler
        4. Extract context updates
        5. Return conversational response
        """
        # Get or create context
        context = self.context_manager.get_context(session_id)
        
        # Step 1: Classify intent
        intent = await self._classify_intent(message, context)
        logger.info(f"Intent classified: {intent} for session {session_id}")
        
        # Step 2: Route to handler
        if intent == "SEARCH":
            result = await self._handle_search(message, context, df)
        elif intent == "ADVICE":
            result = await self._handle_advice(message, context, df)
        elif intent == "CLARIFY":
            result = await self._handle_clarification(message, context)
        elif intent == "QUOTE":
            result = await self._handle_quote(message, context)
        elif intent == "GREETING":
            result = await self._handle_greeting(message, context)
        else:
            # Default to search
            result = await self._handle_search(message, context, df)
        
        # Step 3: Update context
        context.increment_turn(intent, message)
        if result.get("products"):
            for p in result["products"]:
                context.add_product(p.get("part_number", "unknown"), result.get("headline", ""))
        
        # Step 4: Return formatted response
        return {
            "response": result.get("response_text", result.get("response", "")),
            "intent": intent,
            "headline": result.get("headline", ""),
            "recommendations": result.get("recommendations", []),
            "follow_up": result.get("follow_up", ""),
            "products": result.get("products", []),
            "context": context.format_for_prompt(),
            "cost": result.get("cost", "$0"),
            "turn": context.turn_count,
        }
    
    async def _classify_intent(self, message: str, context: ConversationContext) -> str:
        """Classify into 5 conversational categories."""
        prompt = get_prompt(
            "router",
            context=context.format_for_prompt()
        )
        
        try:
            result = await route_message(prompt, message)
            intent = result.strip().upper()
            
            # Validate intent
            valid_intents = ["SEARCH", "ADVICE", "CLARIFY", "QUOTE", "GREETING"]
            if intent not in valid_intents:
                # Try to map legacy intents
                if intent in ["LOOKUP", "PRICE", "COMPARE", "MANUFACTURER", "CHEMICAL", "APPLICATION"]:
                    intent = "SEARCH"
                elif intent in ["PREGAME", "SYSTEM_QUOTE", "DEMO"]:
                    intent = "ADVICE"
                elif intent in ["HELP"]:
                    intent = "GREETING"
                else:
                    intent = "SEARCH"  # Default
            
            return intent
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return "SEARCH"  # Safe default
    
    async def _handle_search(self, message: str, context: ConversationContext, df) -> Dict:
        """Handle product search with conversational response."""
        # Use Voice Gate for product lookup
        gate_result = self.voice_gate.lookup(message)
        
        if not gate_result.found:
            return {
                "response_text": f"I couldn't find products matching '{message}'. Try a part number or describe the application.",
                "headline": "No matches found",
                "recommendations": [],
                "follow_up": "What application are you working on? I can suggest filters.",
                "products": [],
                "cost": "$0",
            }
        
        # Get product details
        products = []
        if gate_result.products:
            products = gate_result.products[:5]  # Max 5 recommendations
        elif gate_result.product:
            products = [gate_result.product]
        
        # Build conversational response
        headline = f"Found {len(products)} option{'s' if len(products) > 1 else ''} for {context.application or 'your application'}"
        
        recommendations = []
        for i, p in enumerate(products, 1):
            reason = self._generate_reasoning(p, context)
            recommendations.append({
                "rank": i,
                "part_number": p.get("Part_Number", "Unknown"),
                "description": p.get("Description", ""),
                "price": p.get("Price", None),
                "in_stock": p.get("In_Stock", None),
                "reasoning": reason,
            })
        
        # Generate follow-up question
        follow_up = self._generate_follow_up(context, products)
        
        # Format full response
        response_lines = [f"**{headline}**", ""]
        for rec in recommendations:
            response_lines.append(f"{rec['rank']}. **{rec['part_number']}** — {rec['description'][:60]}")
            if rec['price'] and rec['price'] > 0:
                response_lines.append(f"   Price: ${rec['price']:.2f}")
            response_lines.append(f"   {rec['reasoning']}")
            response_lines.append("")
        
        response_lines.append(f"*{follow_up}*")
        
        return {
            "response_text": "\n".join(response_lines),
            "headline": headline,
            "recommendations": recommendations,
            "follow_up": follow_up,
            "products": products,
            "cost": "$0",  # Voice Gate search is free
        }
    
    async def _handle_advice(self, message: str, context: ConversationContext, df) -> Dict:
        """Handle advice/recommendation requests."""
        # Similar to search but with more reasoning
        prompt = get_prompt(
            "response",
            context=context.format_for_prompt(),
            products="[Will be populated from search results]",
            query=message
        )
        
        messages = [{"role": "user", "content": message}]
        
        try:
            response = await reason(prompt, messages, temperature=0.4, max_tokens=800)
            
            return {
                "response_text": response,
                "headline": "Recommendations for your application",
                "recommendations": [],
                "follow_up": "Does this help? I can narrow it down further.",
                "products": [],
                "cost": "~$0.02",
            }
        except Exception as e:
            logger.error(f"Advice handling error: {e}")
            return {
                "response_text": "I'd recommend checking in with the office for detailed application guidance.",
                "headline": "Need more information",
                "recommendations": [],
                "follow_up": "What specific application are you working on?",
                "products": [],
                "cost": "$0",
            }
    
    async def _handle_clarification(self, message: str, context: ConversationContext) -> Dict:
        """Ask clarifying question."""
        prompt = get_prompt(
            "clarification",
            context=context.format_for_prompt(),
            query=message
        )
        
        try:
            question = await route_message(prompt, message)
            
            context.needs_clarification = True
            context.open_questions.append(question)
            
            return {
                "response_text": question,
                "headline": "Need a bit more info",
                "recommendations": [],
                "follow_up": question,
                "products": [],
                "cost": "$0",
            }
        except Exception as e:
            logger.error(f"Clarification error: {e}")
            return {
                "response_text": "Could you tell me more about the application? That'll help me recommend the right filters.",
                "headline": "Need clarification",
                "recommendations": [],
                "follow_up": "What industry or application is this for?",
                "products": [],
                "cost": "$0",
            }
    
    async def _handle_quote(self, message: str, context: ConversationContext) -> Dict:
        """Handle quote-building requests."""
        # Extract company name if mentioned
        # For now, guide them to the Quote Builder
        
        return {
            "response_text": "I'll help you build a quote. Click the Quote button on the right, or tell me the company name and products you need.",
            "headline": "Quote Builder ready",
            "recommendations": [],
            "follow_up": "What's the company name, and which products do you want to include?",
            "products": [],
            "cost": "$0",
        }
    
    async def _handle_greeting(self, message: str, context: ConversationContext) -> Dict:
        """Handle casual greetings."""
        greetings = {
            "hello": "Hi there! Ready to help you find the right filtration products. What are you working on?",
            "hi": "Hey! What can I help you find today?",
            "thanks": "You're welcome! Need anything else?",
            "thank you": "Happy to help! What else can I do for you?",
            "help": "I'm here to help you find filtration products, compare options, or build quotes. What do you need?",
        }
        
        lower = message.lower().strip()
        response = greetings.get(lower, "How can I help you today?")
        
        # If this is first greeting and we have context, acknowledge it
        if context.turn_count == 0 and (context.customer_type or context.application):
            response += f"\n\nI see you were working on {context.application or 'something'} for {context.customer_type or 'a customer'}. Picking up where we left off?"
        
        return {
            "response_text": response,
            "headline": "Ready to help",
            "recommendations": [],
            "follow_up": "What application are you working on?",
            "products": [],
            "cost": "$0",
        }
    
    def _generate_reasoning(self, product: Dict, context: ConversationContext) -> str:
        """Generate why this product fits the customer's needs."""
        reasons = []
        
        # Match to application
        if context.application and product.get("Application"):
            if context.application.lower() in str(product.get("Application", "")).lower():
                reasons.append(f"designed for {context.application}")
        
        # Specs match
        if context.specs.get("micron") and product.get("Micron_Rating"):
            reasons.append(f"{product.get('Micron_Rating')} micron rating")
        
        # Stock status
        if product.get("In_Stock"):
            reasons.append("in stock")
        
        if reasons:
            return "Good fit because " + ", ".join(reasons)
        return "Matches your requirements"
    
    def _generate_follow_up(self, context: ConversationContext, products: List[Dict]) -> str:
        """Generate a contextual follow-up question."""
        if not context.specs.get("micron"):
            return "What micron rating do you need?"
        
        if not context.application:
            return "What's the application — HVAC, hydraulic, or something else?"
        
        if len(products) > 1:
            return "Want me to compare these options, or do you need pricing on a specific one?"
        
        return "Need specs, cross-references, or pricing on this?"


# Singleton instance
_conversational_router: Optional[ConversationalRouter] = None

def get_conversational_router(voice_gate: VoiceGate) -> ConversationalRouter:
    """Get or create the conversational router singleton."""
    global _conversational_router
    if _conversational_router is None:
        _conversational_router = ConversationalRouter(voice_gate)
    return _conversational_router
