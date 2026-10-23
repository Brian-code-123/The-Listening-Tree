import subprocess
import sys

import pytest

from app.services import transcription


def test_importing_the_app_does_not_load_speech_recognition():
    """SpeechRecognition is ~40MB and only the /transcribe fallback needs it;
    importing it at module load made every serverless cold start pay for it."""
    code = (
        "import sys; import app.services.transcription; "
        "sys.exit(1 if 'speech_recognition' in sys.modules else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={"SKIP_ENV_LOCAL": "1", "DATABASE_URL": "postgresql://x@127.0.0.1:5432/x", "PYTHONPATH": "."},
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_fallback_reports_a_missing_dependency_clearly(monkeypatch):
    monkeypatch.setitem(sys.modules, "speech_recognition", None)  # import raises ImportError
    with pytest.raises(RuntimeError, match="SpeechRecognition"):
        transcription.transcribe_with_google_fallback(b"", "en")


def _fake_sr(recognize):
    import types

    class UnknownValueError(Exception):
        pass

    class RequestError(Exception):
        pass

    class _AudioFile:
        def __init__(self, _stream):
            pass

        def __enter__(self):
            return object()

        def __exit__(self, *exc):
            return False

    class _Recognizer:
        def record(self, _source):
            return b"audio"

        def recognize_google(self, _audio, language="en-US"):
            return recognize(UnknownValueError, RequestError)

    return types.SimpleNamespace(
        Recognizer=_Recognizer, AudioFile=_AudioFile, UnknownValueError=UnknownValueError, RequestError=RequestError
    )


def test_unintelligible_audio_becomes_a_speech_unintelligible_error(monkeypatch):
    def _raise(unknown, _request):
        raise unknown()

    monkeypatch.setitem(sys.modules, "speech_recognition", _fake_sr(_raise))
    with pytest.raises(transcription.SpeechUnintelligible):
        transcription.transcribe_with_google_fallback(b"x", "en-US")


def test_upstream_failure_becomes_a_speech_service_error(monkeypatch):
    def _raise(_unknown, request_error):
        raise request_error("quota")

    monkeypatch.setitem(sys.modules, "speech_recognition", _fake_sr(_raise))
    with pytest.raises(transcription.SpeechServiceError):
        transcription.transcribe_with_google_fallback(b"x", "en-US")


def test_missing_dependency_is_its_own_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "speech_recognition", None)
    with pytest.raises(transcription.SttDependencyMissing):
        transcription.transcribe_with_google_fallback(b"", "en")


def test_google_fallback_does_not_block_the_event_loop(monkeypatch):
    import asyncio
    import time

    from app.routers import chat as chat_router

    monkeypatch.setattr(chat_router.stt, "HF_API_KEY", "")

    def slow(content, language):
        time.sleep(0.3)
        return "hello"

    monkeypatch.setattr(chat_router.stt, "transcribe_with_google_fallback", slow)

    async def run():
        ticks = 0

        async def heartbeat():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        beat = asyncio.create_task(heartbeat())
        resp = await chat_router._run_stt(b"x", "en-US", "en")
        beat.cancel()
        return resp, ticks

    resp, ticks = asyncio.run(run())
    assert resp.status_code == 200
    assert ticks >= 10  # the loop kept running during the 0.3 s call
