"""
Voice Handler V3 - Simplified
Replaces: voice_echo.py (41KB) + voice_gate.py + voice_search.py

New Flow:
Azure Speech-to-Text → MastermindV3 → Response
"""

import json
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("enpro.voice_v3")


@dataclass
class VoiceResult:
    heard: str
    response: str
    products: list
    confidence: float


class VoiceHandlerV3:
    """
    Simplified voice handling.
    
    OLD: 4-tier lookup → deferred response → predictive prefetch → 32 second delay
    NEW: Transcribe → Unified Handler → Immediate Response
    """
    
    def __init__(self, mastermind):
        self.mastermind = mastermind
        
        # Azure Speech config (simplified for now, can add custom model later)
        self.speech_config = {
            "endpoint": "https://enpro-speech.cognitiveservices.azure.com/",
            "region": "southcentralus",
            "language": "en-US"
        }
    
    async def handle_voice(self, audio_bytes: bytes, session_id: str) -> VoiceResult:
        """
        Simplified voice flow:
        1. Transcribe audio
        2. Pass to MastermindV3
        3. Return conversational response
        """
        # Step 1: Transcribe (use existing Azure Speech for now)
        # TODO: Replace with Azure AI Speech SDK when ready
        transcription = await self._transcribe(audio_bytes)
        
        # Step 2: Get conversation history
        from conversation_memory import read_history
        history = read_history(session_id)[-3:]  # Last 3 for voice context
        
        # Step 3: Unified handler (same as text!)
        result = await self.mastermind.chat(
            message=transcription["text"],
            history=history
        )
        
        return VoiceResult(
            heard=transcription["text"],
            response=result["response"],
            products=result.get("products", []),
            confidence=transcription.get("confidence", 0.8)
        )
    
    async def _transcribe(self, audio_bytes: bytes) -> Dict:
        """
        Transcribe audio using Azure Speech.
        For now, keep existing Whisper integration, migrate to Azure Speech later.
        """
        # Placeholder - integrate your existing azure_whisper call here
        # Or use: from azure.cognitiveservices.speech import SpeechRecognizer
        
        # For immediate deployment, use your existing transcription
        return {
            "text": "HC9600 price",  # Replace with actual transcription
            "confidence": 0.95
        }


# FastAPI endpoint for voice
from fastapi import APIRouter, UploadFile, File

voice_router = APIRouter()

voice_handler: Optional[VoiceHandlerV3] = None

def init_voice_handler(mastermind):
    global voice_handler
    voice_handler = VoiceHandlerV3(mastermind)


@voice_router.post("/voice/chat")
async def voice_chat_endpoint(
    audio: UploadFile = File(...),
    session_id: str = ""
):
    """Simplified voice endpoint."""
    if voice_handler is None:
        return {"error": "Voice handler not initialized"}
    
    audio_bytes = await audio.read()
    result = await voice_handler.handle_voice(audio_bytes, session_id)
    
    return {
        "heard": result.heard,
        "response": result.response,
        "products": result.products,
        "confidence": result.confidence
    }
