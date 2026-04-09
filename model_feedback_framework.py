"""
Multi-Model Feedback Framework for Enpro Portal v2.16
Crowdsource UI/UX and architecture decisions from multiple Azure OpenAI models
"""

import asyncio
import json
import os
from typing import List, Dict, Any
from dataclasses import dataclass
from azure_client import chat_completion
from config import settings

@dataclass
class ModelFeedback:
    model_name: str
    category: str  # 'ui_ux', 'model_selection', 'architecture'
    feedback: str
    recommendations: List[str]
    priority_score: int  # 1-10
    confidence: float  # 0.0-1.0


class MultiModelFeedbackFramework:
    """
    Query multiple Azure OpenAI models and aggregate their feedback
    """
    
    def __init__(self):
        # Define the models we want feedback from
        # User can configure these with their API endpoints
        self.models = {
            'gpt-4.1': settings.AZURE_DEPLOYMENT_REASONING,
            'gpt-4.1-mini': settings.AZURE_DEPLOYMENT_ROUTER,
            # Add more as user provides endpoints:
            # 'o3-mini': 'o3-mini',
            # 'gpt-4.1-nano': 'gpt-4.1-nano',
        }
        
    async def evaluate_ui_ux(self, current_ui_description: str) -> List[ModelFeedback]:
        """
        Get UI/UX feedback from multiple models
        """
        prompt = f"""You are a UX expert evaluating an industrial B2B voice-enabled product search application.

CURRENT UI ELEMENTS TO EVALUATE:
{current_ui_description}

Evaluate the following aspects and provide structured feedback:

1. MOBILE-FIRST DESIGN (reps use this on phones in the field)
   - Are elements thumb-friendly?
   - Is text readable on small screens?
   - Is the voice interaction smooth?

2. CONVERSATIONAL FLOW
   - Does it feel like talking to a knowledgeable colleague?
   - Are there friction points in the interaction?
   - Is context maintained appropriately?

3. INFORMATION DENSITY
   - Is too much or too little information shown?
   - Are product cards scannable?
   - Is the chat history useful?

4. VOICE INTERACTION
   - Is the voice feedback appropriate?
   - Are there voice-specific UX issues?

5. SPECIFIC ELEMENTS TO REVIEW:
   - Quote Builder modal (3-step process)
   - History sidebar (Recent Searches, Flagged Reports, Session Stats, buttons)
   - Bottom admin stats bar (Queries, Cost, Latency, Errors, Reports)
   - File attachment button (currently disabled)
   - Help function accessibility

OUTPUT FORMAT (JSON):
{{
    "overall_assessment": "Brief summary of UX quality (1-2 sentences)",
    "strengths": ["strength 1", "strength 2"],
    "critical_issues": ["issue 1", "issue 2"],
    "recommendations": [
        {{"action": "specific action", "rationale": "why", "priority": "high/medium/low"}},
    ],
    "priority_score": 8,  # 1-10, how urgent are changes needed
    "confidence": 0.9  # 0.0-1.0
}}
"""
        return await self._query_all_models('ui_ux', prompt)
    
    async def evaluate_model_selection(self, use_cases: List[Dict]) -> List[ModelFeedback]:
        """
        Get recommendations on which Azure OpenAI models to use for different tasks
        """
        use_cases_str = json.dumps(use_cases, indent=2)
        
        prompt = f"""You are an AI architecture expert specializing in Azure OpenAI.

CURRENT USE CASES:
{use_cases_str}

AVAILABLE MODELS TO EVALUATE:
- gpt-4.1 (current reasoning model)
- gpt-4.1-mini (current router/model)
- gpt-4.1-nano (potential new option)
- o3-mini (potential new option - better reasoning)
- o1 (potential for complex tasks)

EVALUATE EACH USE CASE:
1. Intent Classification (routing user queries)
2. Product Parameter Extraction (from voice/text)
3. Conversational Response Generation (the "colleague" experience)
4. Chemical Compatibility Analysis
5. Quote/Context Reasoning

For each use case, recommend:
- Best model
- Rationale (speed vs quality tradeoff)
- Temperature setting
- Max tokens
- Cost considerations

OUTPUT FORMAT (JSON):
{{
    "recommendations": [
        {{
            "use_case": "name",
            "recommended_model": "model name",
            "rationale": "detailed reasoning",
            "temperature": 0.3,
            "max_tokens": 1024,
            "estimated_cost_per_call": "$0.002",
            "confidence": 0.9
        }}
    ],
    "overall_strategy": "Summary of model selection approach",
    "priority_score": 7,
    "confidence": 0.85
}}
"""
        return await self._query_all_models('model_selection', prompt)
    
    async def evaluate_architecture(self, current_arch: Dict) -> List[ModelFeedback]:
        """
        Get feedback on overall architecture decisions
        """
        arch_str = json.dumps(current_arch, indent=2)
        
        prompt = f"""You are a software architecture expert evaluating a FastAPI-based voice-enabled product portal.

CURRENT ARCHITECTURE:
{arch_str}

EVALUATE:
1. CONVERSATIONAL MEMORY
   - Current: Session-based in-memory storage
   - Is this sufficient for the "knowledgeable colleague" experience?
   - Should we implement persistent conversation history?

2. VOICE ECHO INTEGRATION
   - Voice Echo exists but isn't integrated into main flow
   - Should predictive pre-fetch be enabled by default?
   - How should deferred responses work in the UI?

3. COMMAND vs CONVERSATIONAL
   - Current: Command-based (lookup, pregame, price, compare, etc.)
   - Target: Natural language only
   - Migration strategy?

4. CONTEXT MANAGEMENT
   - How should customer context (data center, HVAC, etc.) be tracked?
   - How many turns should context persist?
   - How to handle context resets?

5. PRODUCT RECOMMENDATION ENGINE
   - Current: Returns counts and lists
   - Target: 3-5 recommendations with reasoning
   - Implementation approach?

OUTPUT FORMAT (JSON):
{{
    "architecture_score": 7,  # 1-10
    "biggest_risk": "Description of main risk",
    "recommendations": [
        {{
            "area": "component name",
            "current_state": "what exists",
            "recommended_change": "what to do",
            "effort": "small/medium/large",
            "impact": "high/medium/low"
        }}
    ],
    "priority_score": 8,
    "confidence": 0.9
}}
"""
        return await self._query_all_models('architecture', prompt)
    
    async def _query_all_models(self, category: str, prompt: str) -> List[ModelFeedback]:
        """Query all configured models and collect feedback"""
        tasks = []
        for model_name, deployment in self.models.items():
            tasks.append(self._query_single_model(model_name, deployment, category, prompt))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        feedback_list = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Error querying model: {result}")
                continue
            feedback_list.append(result)
        
        return feedback_list
    
    async def _query_single_model(self, model_name: str, deployment: str, 
                                   category: str, prompt: str) -> ModelFeedback:
        """Query a single model for feedback"""
        try:
            messages = [
                {"role": "system", "content": "You are an expert consultant providing structured feedback. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            
            response = await chat_completion(
                deployment=deployment,
                messages=messages,
                temperature=0.3,
                max_tokens=2048
            )
            
            content = response["choices"][0]["message"]["content"]
            
            # Parse JSON response
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    raise
            
            # Extract recommendations as list
            recommendations = []
            if 'recommendations' in data:
                for rec in data['recommendations']:
                    if isinstance(rec, dict):
                        recommendations.append(f"{rec.get('action', '')}: {rec.get('rationale', '')}")
                    else:
                        recommendations.append(str(rec))
            
            return ModelFeedback(
                model_name=model_name,
                category=category,
                feedback=data.get('overall_assessment', data.get('overall_strategy', 'No summary provided')),
                recommendations=recommendations,
                priority_score=data.get('priority_score', 5),
                confidence=data.get('confidence', 0.7)
            )
            
        except Exception as e:
            print(f"Error with {model_name}: {e}")
            return ModelFeedback(
                model_name=model_name,
                category=category,
                feedback=f"Error: {str(e)}",
                recommendations=[],
                priority_score=0,
                confidence=0.0
            )
    
    def aggregate_feedback(self, feedback_list: List[ModelFeedback]) -> Dict[str, Any]:
        """
        Aggregate feedback from multiple models into consensus recommendations
        """
        if not feedback_list:
            return {"error": "No feedback received"}
        
        # Group by category
        by_category = {}
        for fb in feedback_list:
            if fb.category not in by_category:
                by_category[fb.category] = []
            by_category[fb.category].append(fb)
        
        aggregated = {}
        
        for category, items in by_category.items():
            # Calculate weighted consensus
            total_confidence = sum(fb.confidence for fb in items)
            avg_priority = sum(fb.priority_score * fb.confidence for fb in items) / total_confidence if total_confidence > 0 else 5
            
            # Collect all recommendations
            all_recommendations = []
            for fb in items:
                all_recommendations.extend(fb.recommendations)
            
            # Simple deduplication (would be better with embeddings)
            unique_recommendations = list(set(all_recommendations))
            
            aggregated[category] = {
                "model_count": len(items),
                "avg_priority_score": round(avg_priority, 1),
                "consensus_confidence": round(total_confidence / len(items), 2),
                "all_feedback": [fb.feedback for fb in items],
                "consensus_recommendations": unique_recommendations[:10],  # Top 10
                "models_consulted": [fb.model_name for fb in items]
            }
        
        return aggregated


# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """
    Example usage - run this after providing Azure API credentials
    """
    framework = MultiModelFeedbackFramework()
    
    # Define current state
    current_ui = """
    HEADER: Logo badge "Ep" + "Enpro Filtration Mastermind" + Version V2.0
    
    QUICK ACTIONS BAR: Help, Lookup, Pregame, Compare, Reset buttons
    
    MAIN CHAT: Message bubbles (user right, bot left), product cards, typing indicator
    
    LEFT SIDEBAR (History): 
    - Recent Searches (clickable history items)
    - Flagged Reports (empty section)
    - Session Stats (query count, etc.)
    - Action buttons: Email Reports, Download, Clear
    
    RIGHT PANEL: Quote Builder (collapsible, 3-step wizard)
    
    BOTTOM BAR: Admin stats (Queries, Cost $0.00, Avg Latency, Errors, Reports)
    
    INPUT AREA: Text input + Mic button + Attach button (disabled)
    
    MODALS: Lookup, Price, Compare, Chemical, Pregame, Quote Builder
    
    KNOWN ISSUES:
    - Voice repeats back transcript: "I heard: '...'"
    - Help button opens modal but "Go" doesn't work
    - File attachment button disabled
    """
    
    use_cases = [
        {"name": "Intent Classification", "current_model": "gpt-4.1-mini", "latency_sla": "<200ms"},
        {"name": "Parameter Extraction", "current_model": "gpt-4.1-mini", "complexity": "medium"},
        {"name": "Conversational Response", "current_model": "gpt-4.1", "requires_reasoning": True},
        {"name": "Chemical Analysis", "current_model": "gpt-4.1", "requires_accuracy": True},
    ]
    
    current_arch = {
        "backend": "FastAPI + Pandas",
        "ai_models": "Azure OpenAI (gpt-4.1, gpt-4.1-mini) + Azure Whisper",
        "memory": "In-memory session dict (resets on restart)",
        "voice_echo": "Built but not integrated into main flow",
        "product_search": "5-column cascade with fuzzy matching",
        "context_tracking": "Quote state + limited session context"
    }
    
    print("=" * 60)
    print("MULTI-MODEL FEEDBACK FRAMEWORK")
    print("=" * 60)
    print("\nGathering feedback from multiple Azure OpenAI models...\n")
    
    # Query all models
    ui_feedback = await framework.evaluate_ui_ux(current_ui)
    model_feedback = await framework.evaluate_model_selection(use_cases)
    arch_feedback = await framework.evaluate_architecture(current_arch)
    
    # Aggregate
    all_feedback = ui_feedback + model_feedback + arch_feedback
    consensus = framework.aggregate_feedback(all_feedback)
    
    # Print results
    print(json.dumps(consensus, indent=2))
    
    # Save to file
    with open("model_feedback_report.json", "w") as f:
        json.dump(consensus, f, indent=2)
    
    print("\n✅ Report saved to model_feedback_report.json")


if __name__ == "__main__":
    asyncio.run(main())
