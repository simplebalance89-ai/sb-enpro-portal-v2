"""
Voice Part Number Resolution
Azure Speech-to-Text + GPT-5.4 Mini for phonetic part resolution
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .model_router import ModelRouter, ModelTier

logger = logging.getLogger("enpro.models.voice")


@dataclass
class VoiceResolutionResult:
    """Result from voice part resolution."""
    heard: str                    # Raw transcription
    resolved: Optional[str]      # Resolved part number
    confidence: float
    alternatives: List[str]      # Alternative part numbers
    phonetic_match_score: float
    model_used: str
    cost: float


class VoicePartResolver:
    """
    Resolves phonetic part numbers from voice to actual catalog parts.
    
    Pipeline:
    1. Azure Speech-to-Text (phonetic-optimized model)
    2. GPT-5.4 Mini resolves "aitch see ninety six oh oh" → HC9600
    3. Validate against catalog
    """
    
    # Common phonetic confusions in industrial part numbers
    PHONETIC_SUBSTITUTIONS = {
        "aitch": "H", "h": "H",
        "see": "C", "sea": "C", "si": "C",
        "jay": "J", "j": "J",
        "kay": "K", "k": "K",
        "em": "M", "m": "M",
        "en": "N", "n": "N",
        "pee": "P", "pea": "P", "p": "P",
        "cue": "Q", "queue": "Q", "q": "Q",
        "are": "R", "r": "R",
        "tee": "T", "tea": "T", "t": "T",
        "you": "U", "u": "U",
        "vee": "V", "v": "V",
        "double you": "W", "w": "W",
        "ex": "X", "x": "X",
        "why": "Y", "y": "Y",
        "zee": "Z", "zed": "Z", "z": "Z",
        "zero": "0", "oh": "0", "o": "0",
        "one": "1", "won": "1",
        "two": "2", "too": "2", "to": "2",
        "three": "3",
        "four": "4", "for": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8", "ate": "8",
        "nine": "9",
        "dash": "-", "hyphen": "-", "minus": "-",
    }
    
    # Common part number patterns in Enpro catalog
    PART_PATTERNS = [
        r'HC\d{4}',           # Pall HC series (HC9600, HC9020)
        r'CLR\d{3}',          # PowerFlow CLR series
        r'POM\d{2}[A-Z]*',    # Parker POM series
        r'EPE-\d{2}-\d',      # EPE format
        r'[A-Z]{2,4}\d{3,6}', # Generic pattern
    ]
    
    RESOLUTION_PROMPT = """Resolve phonetic transcription to part number.

Common Enpro part number formats:
- HC#### (Pall HC series: HC9600, HC9020)
- CLR### (PowerFlow: CLR130, CLR510)
- POM##* (Parker: POM25AP1SH)
- EPE-##-# (EPE format)

EXAMPLES:
- "aitch see ninety six oh oh" → HC9600
- "see el are one thirty" → CLR130
- "pee oh em twenty five" → POM25
- "aitch see ninety oh two oh" → HC9020

OUTPUT FORMAT:
{
  "resolved_part_number": "HC9600",
  "confidence": 0.95,
  "alternatives": ["HC9601", "HC9600F"],
  "reasoning": "'aitch see' = HC, 'ninety six' = 96, 'oh oh' = 00"
}

If uncertain, provide best guess with lower confidence and alternatives."""
    
    def __init__(self, catalog_part_numbers: Optional[List[str]] = None):
        self.router = ModelRouter()
        self.catalog = set(pn.upper() for pn in (catalog_part_numbers or []))
    
    def preprocess_transcription(self, text: str) -> str:
        """
        Pre-process transcription with phonetic substitutions.
        Converts "aitch see ninety six oh oh" → "H C 96 0 0"
        """
        text_lower = text.lower()
        
        # Apply phonetic substitutions
        for phonetic, replacement in sorted(self.PHONETIC_SUBSTITUTIONS.items(), 
                                            key=lambda x: -len(x[0])):  # Longest first
            text_lower = text_lower.replace(phonetic, replacement)
        
        # Clean up
        text_clean = re.sub(r'\s+', ' ', text_lower).strip()
        return text_clean
    
    async def resolve(
        self,
        transcription: str,
        context: Optional[Dict[str, Any]] = None
    ) -> VoiceResolutionResult:
        """
        Resolve phonetic transcription to part number.
        
        Args:
            transcription: Raw transcription from Azure STT
            context: Optional context (recent parts, customer industry, etc.)
        
        Returns:
            VoiceResolutionResult with resolved part number and confidence
        """
        import time
        start_time = time.time()
        
        # Pre-process
        preprocessed = self.preprocess_transcription(transcription)
        
        # Build context
        context_parts = [f"Pre-processed: '{preprocessed}'"]
        if context:
            if context.get("recent_parts"):
                context_parts.append(f"Recent parts mentioned: {context['recent_parts']}")
            if context.get("industry"):
                context_parts.append(f"Industry: {context['industry']}")
        
        message = "\n".join(context_parts)
        
        # Call GPT-5.4 Mini for resolution
        response = await self.router.complete(
            messages=[
                {"role": "system", "content": self.RESOLUTION_PROMPT},
                {"role": "user", "content": message}
            ],
            tier=ModelTier.FAST,  # GPT-5.4-mini
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=256
        )
        
        try:
            data = json.loads(response.content)
            resolved = data.get("resolved_part_number", "").upper().strip()
            confidence = data.get("confidence", 0.5)
            alternatives = [a.upper() for a in data.get("alternatives", [])]
            
            # Validate against catalog if available
            if self.catalog:
                if resolved in self.catalog:
                    confidence = min(1.0, confidence + 0.1)  # Boost for catalog match
                else:
                    # Check alternatives
                    valid_alts = [a for a in alternatives if a in self.catalog]
                    if valid_alts:
                        resolved = valid_alts[0]
                        confidence = 0.8
                    else:
                        confidence *= 0.5  # Penalize for not in catalog
            
            latency_ms = (time.time() - start_time) * 1000
            
            return VoiceResolutionResult(
                heard=transcription,
                resolved=resolved if confidence > 0.5 else None,
                confidence=confidence,
                alternatives=alternatives,
                phonetic_match_score=confidence,
                model_used=response.model_used,
                cost=response.cost_estimate or 0.003
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse voice resolution: {e}")
            return VoiceResolutionResult(
                heard=transcription,
                resolved=None,
                confidence=0.0,
                alternatives=[],
                phonetic_match_score=0.0,
                model_used="error",
                cost=0.0
            )
    
    def resolve_simple(self, text: str) -> Optional[str]:
        """
        Simple rule-based resolution without AI (zero cost).
        Useful for common patterns.
        """
        preprocessed = self.preprocess_transcription(text)
        
        # Remove spaces and check against patterns
        compact = preprocessed.replace(" ", "").replace("-", "")
        
        # Check HC pattern
        hc_match = re.match(r'HC(\d{4})', compact, re.IGNORECASE)
        if hc_match:
            return f"HC{hc_match.group(1)}".upper()
        
        # Check CLR pattern  
        clr_match = re.match(r'CLR(\d{3})', compact, re.IGNORECASE)
        if clr_match:
            return f"CLR{clr_match.group(1)}".upper()
        
        # Check POM pattern
        pom_match = re.match(r'POM(\d{2})', compact, re.IGNORECASE)
        if pom_match:
            return f"POM{pom_match.group(1)}".upper()
        
        return None


# Global instance
_voice_resolver: Optional[VoicePartResolver] = None


def get_voice_resolver(catalog_parts: Optional[List[str]] = None) -> VoicePartResolver:
    """Get the global voice resolver instance."""
    global _voice_resolver
    if _voice_resolver is None:
        _voice_resolver = VoicePartResolver(catalog_parts)
    return _voice_resolver
