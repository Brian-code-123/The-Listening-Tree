import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import chat as chat_router
from tests.integration.test_security_limits import _ask, _signed_in, user  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1")]


def test_crisis_gets_fixed_help_and_never_reaches_the_model(user, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("model must not be called")

    events = []

    async def spy(event, **kw):
        events.append((event, kw))

    monkeypatch.setattr(chat_router, "call_ai", boom)
    monkeypatch.setattr(chat_router, "record_event", spy)
    with TestClient(app) as client:
        _signed_in(client, user)
        reply = _ask(client, "我想死").json()["response"]
    assert "2896 0000" in reply
    assert events and events[0][0] == "safety_trigger"
    assert "我想死" not in str(events[0][1])


def test_scam_goes_to_the_model_with_a_warning(user, monkeypatch):
    seen = {}

    async def fake(c, text, uid, lang, **kw):
        seen.update(kw)
        return "ok"

    monkeypatch.setattr(chat_router, "call_ai", fake)
    with TestClient(app) as client:
        _signed_in(client, user)
        _ask(client, "有人叫我轉帳領獎")
    assert "18222" in (seen.get("extra_system") or "")
