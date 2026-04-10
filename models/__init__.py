"""
Modular AI Model Router for Enpro Filtration Mastermind Portal
Provides specialized model routing based on task complexity and type.

Sales-First Architecture:
- Pregame: o3-mini-high (strategic reasoning with visible trace)
- Compare: o3-mini (side-by-side reasoning)
- Voice Lookup: GPT-5.4 Mini (phonetic resolution)
- Quote Extraction: GPT-5.4 Mini (entity extraction)
- Chemical: Hardcoded lookup (zero AI cost)
- Intent: Phi-4 or pattern matching (ultra-low cost)
"""

from .model_router import ModelRouter, get_model_router, ModelTier, ModelResponse
from .reasoning_engine import ReasoningEngine, ReasoningResult
from .classifier import IntentClassifier
from .chemical_expert import ChemicalExpert, get_chemical_expert
from .voice_resolver import VoicePartResolver, get_voice_resolver, VoiceResolutionResult

__all__ = [
    # Router
    "ModelRouter",
    "get_model_router",
    "ModelTier",
    "ModelResponse",
    # Specialized engines
    "ReasoningEngine",
    "ReasoningResult",
    "IntentClassifier",
    "ChemicalExpert",
    "get_chemical_expert",
    "VoicePartResolver",
    "get_voice_resolver",
    "VoiceResolutionResult",
]
