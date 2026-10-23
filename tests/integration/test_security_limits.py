import asyncio
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.core import body_limit
from app.db import pool as db_pool
from app.routers import chat as chat_router
from app.routers import hk_guide as hk_router
from app.services import hk_guide_data, reminders as reminder_service
from run import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]
JSON_H = {"accept": "application/json"}


@pytest.fixture
def user():
    email = f"lim_{uuid.uuid4().hex[:10]}@example.com"
    create_user_direct(email)
    yield email
    delete_user_direct(email)


def _signed_in(client, email):
    assert client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON_H).json()["success"] is True


def _ask(client, text):
    return client.post("/get_response", data={"msg": text})


# --- chat messages --------------------------------------------------------

def test_a_message_has_a_size_limit(user):
    with TestClient(app) as client:
        _signed_in(client, user)
        assert _ask(client, "x" * 2000).status_code == 200
        assert _ask(client, "x" * 2001).status_code == 422


def test_an_empty_or_blank_message_is_refused_politely(user):
    with TestClient(app) as client:
        _signed_in(client, user)
        resp = _ask(client, "   \n  ")
        assert resp.status_code == 400
        assert "Please enter a message" in resp.json()["response"]


def test_a_flood_of_messages_is_slowed_per_user(user, monkeypatch):
    # 21 live requests take ~50s; a 60s fixed window can roll over mid-test.
    monkeypatch.setattr(chat_router, "CHAT_USER_WINDOW_SECONDS", 10**9)
    with TestClient(app) as client:
        _signed_in(client, user)
        codes = [_ask(client, "hello").status_code for _ in range(21)]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429


def test_there_is_a_daily_cap_per_user(user, monkeypatch):
    monkeypatch.setattr(chat_router, "CHAT_USER_LIMIT", 100)
    monkeypatch.setattr(chat_router, "CHAT_USER_DAILY", 3)
    with TestClient(app) as client:
        _signed_in(client, user)
        assert [_ask(client, "hello").status_code for _ in range(4)] == [200, 200, 200, 429]


# --- reminders ------------------------------------------------------------

def test_active_reminders_are_capped(user, monkeypatch):
    monkeypatch.setattr(reminder_service, "MAX_ACTIVE_REMINDERS", 3)
    with TestClient(app) as client:
        _signed_in(client, user)
        made = [client.post("/reminders", data={"label": f"pill {i}", "time": "09:00"}).status_code for i in range(4)]
        assert made == [200, 200, 200, 400]
        assert "limit" in client.post("/reminders", data={"label": "one more", "time": "09:00"}).json()["message"].lower()
        chat = _ask(client, "set reminder walk 10:00").json()["response"]
        assert "limit" in chat.lower() or "上限" in chat


def test_a_reminder_label_has_a_size_limit(user):
    with TestClient(app) as client:
        _signed_in(client, user)
        assert client.post("/reminders", data={"label": "x" * 100, "time": "09:00"}).status_code == 200
        assert client.post("/reminders", data={"label": "x" * 101, "time": "09:00"}).status_code == 422
        reply = _ask(client, "set reminder " + "y" * 150 + " 10:00").json()["response"]
        assert "too long" in reply.lower() or "太長" in reply


def test_one_user_cannot_touch_anothers_reminders(user):
    other = f"lim_{uuid.uuid4().hex[:10]}@example.com"
    create_user_direct(other)
    try:
        with TestClient(app) as client:
            _signed_in(client, user)
            rid = client.post("/reminders", data={"label": "mine", "time": "09:00"}).json()["id"]
            client.cookies.clear()
            _signed_in(client, other)
            assert client.delete(f"/reminders/{rid}").status_code == 404
            client.post("/deactivate_reminder", data={"label": "mine"})
            client.cookies.clear()
            _signed_in(client, user)
            kept = client.get("/get_reminders").json()["reminders"]
            assert [r["label"] for r in kept] == ["mine"] and kept[0]["active"]
    finally:
        delete_user_direct(other)


# --- preferences ----------------------------------------------------------

def test_only_known_preferences_can_be_set(user):
    with TestClient(app) as client:
        _signed_in(client, user)
        assert "Unknown preference" in _ask(client, "set preference whatever value").json()["response"]
        assert "Unknown preference" in _ask(client, "set preference language klingon").json()["response"]
        assert "language = zh-HK" in _ask(client, "set preference language zh-hk").json()["response"]


# --- ids and sizes --------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("post", "/conversations/9999999999999999999/pin"),
    ("delete", "/conversations/9999999999999999999"),
    ("get", "/conversations/9999999999999999999/messages"),
    ("delete", "/reminders/99999999999999999999"),
    ("get", "/conversations/0/messages"),
])
def test_out_of_range_ids_are_a_422_not_a_server_error(user, method, path):
    with TestClient(app, raise_server_exceptions=False) as client:
        _signed_in(client, user)
        assert getattr(client, method)(path).status_code == 422


def test_a_non_numeric_content_length_is_a_400_not_a_500(user):
    with TestClient(app, raise_server_exceptions=False) as client:
        _signed_in(client, user)
        resp = client.post("/transcribe", content=b"x", headers={"content-length": "abc", "content-type": "audio/wav"})
        assert resp.status_code == 400


def test_oversized_bodies_are_refused_before_they_are_parsed(user, monkeypatch):
    monkeypatch.setattr(body_limit, "DEFAULT_MAX_BODY_BYTES", 10_000)
    monkeypatch.setattr(body_limit, "UPLOAD_MAX_BODY_BYTES", 50_000)
    with TestClient(app) as client:
        _signed_in(client, user)
        assert client.post("/get_response", data={"msg": "hi" + "a" * 20_000}).status_code == 413

        def chunks():
            for _ in range(5):
                yield b"a" * 5_000  # no Content-Length: sent chunked

        assert client.post("/get_response", content=chunks(), headers={"content-type": "application/x-www-form-urlencoded"}).status_code == 413
        big_audio = {"audio": ("v.wav", b"RIFF" + b"0" * 60_000, "audio/wav")}
        assert client.post("/transcribe", files=big_audio).status_code == 413


# --- public data endpoints ------------------------------------------------

def test_a_signed_out_visitor_cannot_force_the_guide_to_recompute(monkeypatch, user):
    calls = []
    real = hk_router.get_hk_guide_data
    monkeypatch.setattr(hk_router, "get_hk_guide_data", lambda lang: calls.append(lang) or real(lang))
    hk_router._hk_guide_cache.update(data=None, timestamp=0, lang=None)
    with TestClient(app) as client:
        client.get("/get_hk_guide")
        before = len(calls)
        for _ in range(3):
            client.get("/get_hk_guide?refresh=1")
        assert len(calls) == before  # refresh ignored when signed out
        _signed_in(client, user)
        client.get("/get_hk_guide?refresh=1")
        assert len(calls) == before + 1


def test_public_data_endpoints_are_limited_per_address(monkeypatch):
    async def fake_news(lang):
        return []

    monkeypatch.setattr(hk_router, "fetch_hk_news", fake_news)
    monkeypatch.setattr(hk_router, "PUBLIC_DATA_LIMIT", 30)
    with TestClient(app) as client:
        codes = [client.get("/get_news").status_code for _ in range(31)]
    assert codes[:30] == [200] * 30
    assert codes[30] == 429


def test_the_news_api_key_travels_in_a_header_not_the_url(monkeypatch):
    seen = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"articles": []}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            seen.update(url=url, params=params or {}, headers=headers or {})
            return _Resp()

    monkeypatch.setattr(hk_guide_data, "NEWS_API_KEY", "secret-key")
    monkeypatch.setattr(hk_guide_data.httpx, "AsyncClient", _Client)
    hk_guide_data._news_cache.update(data=None, timestamp=0, lang=None)
    asyncio.run(hk_guide_data.fetch_hk_news("en"))
    assert "apiKey" not in seen["params"] and "secret-key" not in seen["url"]
    assert seen["headers"].get("X-Api-Key") == "secret-key"


# --- resilience -----------------------------------------------------------

def test_a_failing_model_call_does_not_leak_a_database_connection(user, monkeypatch):
    from app.db import pool as db_pool

    async def broken(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(chat_router, "call_ai", broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        _signed_in(client, user)
        for _ in range(3):
            assert _ask(client, "tell me a story").status_code == 500
        assert db_pool.POOL.get_size() - db_pool.POOL.get_idle_size() == 0  # every connection came back
        monkeypatch.undo()
        assert client.get("/me").status_code == 200  # and the app still serves
