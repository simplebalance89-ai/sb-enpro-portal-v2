"""
Voice Handler V3 - Azure Speech Services
Replaces: voice_echo.py (41KB) + voice_gate.py + voice_search.py + Whisper

Flow: Azure Speech STT → MastermindV3 → Response
"""

import io
import json
import logging
import os
import tempfile
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("enpro.voice_v3")

# Azure Speech config from environment
SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY", "")
SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION", "eastus")

# Industrial part number vocabulary for custom phrase list
PART_NUMBER_PHRASES = [
    "HC9600", "HC9601", "HC9604", "HC9650", "HC9700", "HC9800", "HC9801",
    "CLR130", "CLR132", "CLR140", "CLR150",
    "POM25", "POM10", "POM5",
    "UE619", "UE319", "UE219",
    "EPE", "PEPE", "SBF", "SOFF",
    "Pall", "Donaldson", "Parker", "Filtrox", "Schroeder", "Mahle",
    "PTFE", "Viton", "EPDM", "Buna-N", "polypropylene", "polyester",
    "micron", "PSI", "GPM",
]


@dataclass
class VoiceResult:
    heard: str
    response: str
    products: list
    confidence: float


class VoiceHandlerV3:
    """
    Azure Speech Services voice handler.

    Uses Azure Speech SDK for real-time transcription with custom phrase list
    for industrial part numbers. Falls back to Whisper if Speech SDK unavailable.
    """

    def __init__(self, mastermind):
        self.mastermind = mastermind
        self._speech_available = False

        try:
            import azure.cognitiveservices.speech as speechsdk
            self._speechsdk = speechsdk
            if SPEECH_KEY:
                self._speech_config = speechsdk.SpeechConfig(
                    subscription=SPEECH_KEY,
                    region=SPEECH_REGION,
                )
                self._speech_config.speech_recognition_language = "en-US"
                self._speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceResponse_RequestSentimentAnalysis, "false"
                )
                self._speech_available = True
                logger.info(f"Azure Speech Services initialized (region: {SPEECH_REGION})")
            else:
                logger.warning("AZURE_SPEECH_KEY not set — voice will use Whisper fallback")
        except ImportError:
            logger.warning("azure-cognitiveservices-speech not installed — voice will use Whisper fallback")

    async def handle_voice(self, audio_bytes: bytes, session_id: str) -> VoiceResult:
        """
        Voice flow:
        1. Transcribe audio via Azure Speech (or Whisper fallback)
        2. Pass to MastermindV3 (same as text)
        3. Return response
        """
        transcription = await self._transcribe(audio_bytes)

        if not transcription["text"]:
            return VoiceResult(
                heard="",
                response="I didn't catch that. Could you try again?",
                products=[],
                confidence=0.0,
            )

        result = await self.mastermind.chat(
            message=transcription["text"],
            history=[],
        )

        return VoiceResult(
            heard=transcription["text"],
            response=result.get("to_user", result.get("response", "")),
            products=result.get("picks", []),
            confidence=transcription.get("confidence", 0.8),
        )

    async def _transcribe(self, audio_bytes: bytes) -> Dict:
        """Transcribe audio using Azure Speech Services with part number phrase list."""
        if self._speech_available:
            return self._transcribe_azure_speech(audio_bytes)
        return await self._transcribe_whisper(audio_bytes)

    def _transcribe_azure_speech(self, audio_bytes: bytes) -> Dict:
        """Azure Speech SDK transcription with custom phrase list."""
        speechsdk = self._speechsdk

        # Write audio to temp file (SDK needs file or stream)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            audio_config = speechsdk.AudioConfig(filename=temp_path)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self._speech_config,
                audio_config=audio_config,
            )

            # Add custom phrase list for industrial part numbers
            phrase_list = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
            for phrase in PART_NUMBER_PHRASES:
                phrase_list.addPhrase(phrase)

            # Recognize
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                logger.info(f"Azure Speech recognized: {result.text}")
                return {"text": result.text, "confidence": 0.95}
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.warning("Azure Speech: no match")
                return {"text": "", "confidence": 0.0}
            else:
                logger.error(f"Azure Speech error: {result.reason}")
                return {"text": "", "confidence": 0.0}
        finally:
            os.unlink(temp_path)

    async def _transcribe_whisper(self, audio_bytes: bytes) -> Dict:
        """Fallback: Whisper transcription via Azure OpenAI."""
        import httpx

        whisper_endpoint = os.environ.get("AZURE_WHISPER_ENDPOINT", "")
        whisper_key = os.environ.get("AZURE_WHISPER_KEY", "")
        whisper_deployment = os.environ.get("AZURE_WHISPER_DEPLOYMENT", "whisper")
        api_version = os.environ.get("AZURE_WHISPER_API_VERSION", "2024-12-01-preview")

        if not whisper_endpoint or not whisper_key:
            logger.error("No Whisper endpoint configured for fallback")
            return {"text": "", "confidence": 0.0}

        url = f"{whisper_endpoint}openai/deployments/{whisper_deployment}/audio/transcriptions?api-version={api_version}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    headers={"api-key": whisper_key},
                    files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                    data={"response_format": "json"},
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("text", "")
                logger.info(f"Whisper transcription: {text}")
                return {"text": text, "confidence": 0.85}
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return {"text": "", "confidence": 0.0}


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
    session_id: str = "",
):
    """Voice endpoint — Azure Speech STT with Whisper fallback."""
    if voice_handler is None:
        return {"error": "Voice handler not initialized"}

    audio_bytes = await audio.read()
    result = await voice_handler.handle_voice(audio_bytes, session_id)

    return {
        "heard": result.heard,
        "response": result.response,
        "products": result.products,
        "confidence": result.confidence,
    }
