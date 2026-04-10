"""
Azure-Only Model Router
Routes requests to the appropriate Azure model based on task complexity and type.
Uses: GPT-5.4, o3-mini, o3-pro, Phi-4 (Azure AI Foundry)
"""

import json
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx
from config import settings

logger = logging.getLogger("enpro.models.router")


class ModelTier(Enum):
    """Model tiers for different reasoning requirements."""
    FAST = "gpt-5.4-mini"           # Simple lookups, low cost
    STANDARD = "gpt-5.4"             # General reasoning
    REASONING = "o3-mini"            # Complex reasoning with thinking traces
    REASONING_HIGH = "o3-mini-high"  # Deep reasoning for pregames
    SAFETY_CRITICAL = "o3-pro"       # Critical safety checks (hydrogen, >400F, etc.)
    CLASSIFIER = "phi-4"             # Intent classification (Azure AI Foundry)


@dataclass
class ModelResponse:
    """Standardized response from any model."""
    content: str
    model_used: str
    reasoning_trace: Optional[List[str]] = None
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    latency_ms: Optional[float] = None


class ModelRouter:
    """
    Intelligent model router that selects the best Azure model for each task.
    
    Selection criteria:
    - Safety-critical (hydrogen, H2S, >400F, >150 PSI) → o3-pro
    - Complex chemical compatibility with reasoning → o3-mini-high
    - Customer pregame with reasoning trace → o3-mini-high
    - General reasoning → GPT-5.4 (with reasoning effort)
    - Simple lookups → GPT-5.4-mini
    - Intent classification → Phi-4 (Azure AI Foundry)
    """
    
    # Cost per million tokens (approximate Azure pricing)
    COSTS = {
        "gpt-5.4": {"input": 2.50, "output": 10.00},
        "gpt-5.4-mini": {"input": 0.75, "output": 3.00},
        "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
        "o3-mini": {"input": 1.10, "output": 4.40},
        "o3-mini-high": {"input": 1.10, "output": 4.40},
        "o3-pro": {"input": 5.00, "output": 20.00},  # Estimated
        "phi-4": {"input": 0.10, "output": 0.40},    # Azure AI Foundry
    }
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._request_count: Dict[str, int] = {
            tier.value: 0 for tier in ModelTier
        }
        self._token_usage: Dict[str, int] = {
            tier.value: 0 for tier in ModelTier
        }
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get auth headers for Azure OpenAI."""
        headers = {"Content-Type": "application/json"}
        endpoint = settings.AZURE_OPENAI_ENDPOINT
        
        if "services.ai.azure.com" in endpoint:
            headers["Authorization"] = f"Bearer {settings.AZURE_OPENAI_KEY}"
        else:
            headers["api-key"] = settings.AZURE_OPENAI_KEY
        return headers
    
    def _build_url(self, deployment: str) -> str:
        """Build API URL for deployment."""
        endpoint = settings.AZURE_OPENAI_ENDPOINT.rstrip("/")
        
        if "services.ai.azure.com" in endpoint and "/api/projects/" in endpoint:
            return f"{endpoint}/chat/completions"
        else:
            return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    
    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in dollars for the request."""
        costs = self.COSTS.get(model, {"input": 2.50, "output": 10.00})
        input_cost = (prompt_tokens / 1_000_000) * costs["input"]
        output_cost = (completion_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 6)
    
    def select_model_tier(
        self,
        intent: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        requires_reasoning: bool = False,
        safety_critical: bool = False
    ) -> ModelTier:
        """
        Select the appropriate model tier based on task characteristics.
        
        Args:
            intent: Classified intent
            message: User message
            context: Additional context
            requires_reasoning: Whether reasoning trace is required
            safety_critical: Whether this is a safety-critical query
        """
        message_lower = message.lower()
        
        # Tier 1: Safety-critical checks ALWAYS use o3-pro
        if safety_critical or any(kw in message_lower for kw in [
            "hydrogen", "h2s", "500f", "600f", "lethal", "chlorine", "hf", "hydrofluoric"
        ]):
            return ModelTier.SAFETY_CRITICAL
        
        # Tier 2: Complex reasoning tasks
        if requires_reasoning or intent in ["pregame", "system_quote"]:
            return ModelTier.REASONING_HIGH
        
        # Tier 3: Chemical compatibility with hardcoded rules
        if intent == "chemical":
            # Check if it's a complex chemical scenario
            complex_chemicals = ["sulfuric", "concentrated", "mek", "ketone", "aromatic"]
            if any(chem in message_lower for chem in complex_chemicals):
                return ModelTier.REASONING
            return ModelTier.STANDARD
        
        # Tier 4: Intent classification
        if intent == "classify":
            return ModelTier.CLASSIFIER
        
        # Tier 5: Simple lookups
        if intent in ["lookup", "price"]:
            return ModelTier.FAST
        
        # Default: Standard reasoning
        return ModelTier.STANDARD
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        tier: ModelTier,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> ModelResponse:
        """
        Execute completion with the specified model tier.
        
        Args:
            messages: List of message dicts
            tier: Model tier to use
            temperature: Sampling temperature (not used for o3 models)
            max_tokens: Max response tokens
            response_format: JSON schema for structured output
            reasoning_effort: "low", "medium", "high" for reasoning models
        """
        import time
        start_time = time.time()
        
        deployment = tier.value
        url = self._build_url(deployment)
        
        # Build payload
        payload: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
        }
        
        # New Azure AI Foundry endpoint requires model in payload
        if "services.ai.azure.com" in settings.AZURE_OPENAI_ENDPOINT:
            payload["model"] = deployment
        
        # Add temperature for non-reasoning models
        if temperature is not None and "o3" not in deployment:
            payload["temperature"] = temperature
        
        # Add response format for structured output
        if response_format:
            payload["response_format"] = response_format
        
        # Add reasoning effort for o3 models
        if "o3" in deployment and reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        
        # Add reasoning for GPT-5.4
        if "gpt-5.4" in deployment and reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}
        
        logger.debug(f"Model request: tier={tier.name}, deployment={deployment}")
        
        client = await self.get_client()
        response = await client.post(url, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract response content
        choice = data["choices"][0]
        content = choice["message"]["content"]
        
        # Extract reasoning trace if available (o3 models)
        reasoning_trace = None
        if "reasoning_content" in choice["message"]:
            reasoning_trace = [choice["message"]["reasoning_content"]]
        
        # Get token usage
        usage = data.get("usage", {})
        tokens_used = usage.get("total_tokens", 0)
        
        # Calculate metrics
        latency_ms = (time.time() - start_time) * 1000
        cost = self._estimate_cost(
            deployment,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        # Update stats
        self._request_count[deployment] += 1
        self._token_usage[deployment] += tokens_used
        
        return ModelResponse(
            content=content,
            model_used=deployment,
            reasoning_trace=reasoning_trace,
            tokens_used=tokens_used,
            cost_estimate=cost,
            latency_ms=latency_ms
        )
    
    async def route_and_complete(
        self,
        intent: str,
        message: str,
        system_prompt: str,
        context: Optional[Dict[str, Any]] = None,
        requires_reasoning: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse:
        """
        Auto-select model tier and execute completion.
        
        This is the main entry point - it selects the appropriate model
        based on intent and message content, then executes the completion.
        """
        # Check for safety-critical conditions
        safety_critical = self._is_safety_critical(message, context)
        
        # Select model tier
        tier = self.select_model_tier(
            intent=intent,
            message=message,
            context=context,
            requires_reasoning=requires_reasoning,
            safety_critical=safety_critical
        )
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        # Determine reasoning effort
        reasoning_effort = None
        if tier == ModelTier.REASONING_HIGH:
            reasoning_effort = "high"
        elif tier == ModelTier.REASONING:
            reasoning_effort = "medium"
        elif tier == ModelTier.SAFETY_CRITICAL:
            reasoning_effort = "high"
        
        logger.info(f"Routing to {tier.name} for intent={intent}, safety={safety_critical}")
        
        return await self.complete(
            messages=messages,
            tier=tier,
            response_format=response_format,
            reasoning_effort=reasoning_effort
        )
    
    def _is_safety_critical(self, message: str, context: Optional[Dict[str, Any]]) -> bool:
        """Check if the query involves safety-critical conditions."""
        message_lower = message.lower()
        
        # Critical keywords
        critical = [
            "hydrogen", "h2s", "hydrogen sulfide", "sour gas", "nace",
            "500f", "600f", ">400", "chlorine", "hf", "hydrofluoric",
            "lethal", "toxic", "explosive", "steam", "150 psi", ">150 psi"
        ]
        
        for kw in critical:
            if kw in message_lower:
                return True
        
        # Check temperature
        import re
        temp_match = re.search(r'(\d+)\s*f', message_lower)
        if temp_match:
            temp = int(temp_match.group(1))
            if temp > 400:
                return True
        
        # Check pressure
        pressure_match = re.search(r'(\d+)\s*psi', message_lower)
        if pressure_match:
            pressure = int(pressure_match.group(1))
            if pressure > 150:
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all model tiers."""
        return {
            "requests": self._request_count,
            "tokens": self._token_usage,
            "estimated_cost_usd": {
                tier: round(self._token_usage[tier] / 1_000_000 * self.COSTS.get(tier, {}).get("input", 2.50), 4)
                for tier in self._token_usage
            }
        }


# Global router instance
_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
