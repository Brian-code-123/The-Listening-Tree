"""Server-side speech-to-text: Whisper (Hugging Face) primary, Google Web
Speech (via SpeechRecognition) fallback.
"""
import io
import logging
import os

import httpx

logger = logging.getLogger(__name__)


class SttDependencyMissing(RuntimeError):
    """SpeechRecognition is not installed."""


class SpeechUnintelligible(Exception):
    """The audio held no recognisable speech."""


class SpeechServiceError(Exception):
    """The upstream recogniser could not be reached or refused the request."""

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
    # Imported here, not at module load: it is ~40MB and only this fallback
    # needs it, while every serverless cold start would pay for the import.
    try:
        import speech_recognition as sr
    except ImportError:
        raise SttDependencyMissing("Server STT dependency missing (SpeechRecognition).") from None
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(content)) as source:
        audio_data = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio_data, language=language).strip()
    except sr.UnknownValueError as e:
        raise SpeechUnintelligible() from e
    except sr.RequestError as e:
        raise SpeechServiceError(str(e)) from e
