"""Server-side speech-to-text: Whisper (Hugging Face) primary, Google Web
Speech (via SpeechRecognition) fallback.
"""
import io
import logging
import os

import httpx

try:
    import speech_recognition as sr
except ImportError:
    sr = None

logger = logging.getLogger(__name__)

# Hugging Face Inference API — Whisper large-v3 for server-side STT.
HF_API_KEY = os.environ.get("HF_API_KEY")
HF_WHISPER_MODEL = os.environ.get("HF_WHISPER_MODEL") or "openai/whisper-large-v3"
# Generous for a short voice-input clip; caps /transcribe's exposure to a
# memory-exhaustion DoS from a large repeated upload.
MAX_TRANSCRIBE_UPLOAD_BYTES = int(os.environ.get("MAX_TRANSCRIBE_UPLOAD_BYTES") or 10 * 1024 * 1024)
HF_WHISPER_URL = f"https://router.huggingface.co/hf-inference/models/{HF_WHISPER_MODEL}"

if HF_API_KEY:
    logger.info(f"[STT] {HF_WHISPER_MODEL} configured (Hugging Face Inference API)")
else:
    logger.warning("[STT] HF_API_KEY not set — falling back to Google Web Speech / browser STT")


async def transcribe_with_hf_whisper(content: bytes) -> str:
    """Call Hugging Face Inference API (Whisper large-v3). Raises on failure."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            HF_WHISPER_URL,
            headers={
                "Authorization": f"Bearer {HF_API_KEY}",
                "Content-Type": "audio/wav",
            },
            content=content,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "text" in data:
            return data["text"].strip()
        raise ValueError(f"Unexpected Whisper response: {data}")


def transcribe_with_google_fallback(content: bytes, language: str) -> str:
    """Legacy SpeechRecognition + Google Web Speech backend fallback."""
    if sr is None:
        raise RuntimeError("Server STT dependency missing (SpeechRecognition).")
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(content)) as source:
        audio_data = recognizer.record(source)
    return recognizer.recognize_google(audio_data, language=language).strip()
