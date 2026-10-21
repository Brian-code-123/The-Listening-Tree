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
