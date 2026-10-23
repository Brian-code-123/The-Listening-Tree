import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import chat as chat_router
from tests.integration.test_security_limits import _signed_in, user  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1")]
SSE = {"accept": "text/event-stream"}


def _events(text):
    return [json.loads(line[5:]) for line in text.splitlines() if line.startswith("data:")]


def test_reply_arrives_in_pieces_and_is_saved_once(user, monkeypatch):
    async def fake_stream(messages, lang):
        for piece in ("Good ", "morning, ", "friend."):
            yield piece

    monkeypatch.setattr(chat_router, "stream_ai", fake_stream)
    with TestClient(app) as client:
        _signed_in(client, user)
        resp = client.post("/get_response", data={"msg": "hello there"}, headers=SSE)
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = _events(resp.text)
        assert [e.get("delta") for e in events[:3]] == ["Good ", "morning, ", "friend."]
        assert events[-1] == {"done": True, "response": "Good morning, friend."}
        history = client.get("/get_chat_history").json()["history"]
    bots = [m["message"] for m in history if m["sender"] == "bot"]
    assert bots.count("Good morning, friend.") == 1
    assert any(m["message"] == "hello there" for m in history if m["sender"] == "user")


def test_commands_still_answer_plain_json_even_when_a_stream_is_asked_for(user):
    with TestClient(app) as client:
        _signed_in(client, user)
        resp = client.post("/get_response", data={"msg": "set preference language en"}, headers=SSE)
    assert resp.headers["content-type"].startswith("application/json")
    assert "response" in resp.json()


def test_crisis_message_is_never_streamed_from_the_model(user, monkeypatch):
    async def boom(messages, lang):
        raise AssertionError("model must not be called")
        yield  # pragma: no cover

    monkeypatch.setattr(chat_router, "stream_ai", boom)
    with TestClient(app) as client:
        _signed_in(client, user)
        resp = client.post("/get_response", data={"msg": "我想死"}, headers=SSE)
    assert "2896 0000" in resp.json()["response"]


def test_a_stream_that_fails_at_the_start_gives_the_warm_fallback(user, monkeypatch):
    from app.services import ai

    monkeypatch.setattr(ai, "ZHIPU_API_KEY", "")
    with TestClient(app) as client:
        _signed_in(client, user)
        events = _events(client.post("/get_response", data={"msg": "good evening"}, headers=SSE).text)
    assert events[-1]["done"] is True and events[-1]["response"]


def test_a_failing_model_does_not_leak_a_connection_while_streaming(user, monkeypatch):
    from app.db import pool as db_pool

    async def broken(messages, lang):
        raise RuntimeError("boom")
        yield  # pragma: no cover

    monkeypatch.setattr(chat_router, "stream_ai", broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        _signed_in(client, user)
        client.post("/get_response", data={"msg": "hello"}, headers=SSE)
        assert db_pool.POOL.get_size() - db_pool.POOL.get_idle_size() == 0  # nothing left checked out


def test_a_client_that_leaves_mid_reply_still_gets_its_reply_saved_and_frees_the_connection(user, monkeypatch):
    """Starlette cancels the streaming task when the browser disconnects, and
    anyio re-raises the cancellation at every await in the cancelled scope, so
    the save in the generator's `finally` has to be shielded."""
    import asyncio

    import anyio
    import asyncpg

    from app.db import pool as db_pool

    async def slow_stream(messages, lang):
        yield "First sentence. "
        await asyncio.sleep(5)
        yield "never sent"

    monkeypatch.setattr(chat_router, "stream_ai", slow_stream)

    async def run():
        async with app.router.lifespan_context(app):  # the pool lives on this loop
            conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
            uid = (await conn.fetchrow("SELECT id FROM users WHERE email = $1", user))["id"]
            cid = (await conn.fetchrow("INSERT INTO conversations (user_id) VALUES ($1) RETURNING id", uid))["id"]
            gen = chat_router._stream_reply(uid, "en", "2026-01-01 00:00:00", cid, [])

            async def consume():
                async for _ in gen:
                    pass

            # As Starlette does it: the response body is consumed inside a task
            # group, and the group is cancelled when the browser disconnects while
            # the generator is waiting for the model.
            async with anyio.create_task_group() as tg:
                tg.start_soon(consume)
                await anyio.sleep(0.3)
                tg.cancel_scope.cancel()
            saved = await conn.fetch("SELECT message FROM chat_history WHERE conversation_id = $1 AND is_bot", cid)
            in_use_after = db_pool.POOL.get_size() - db_pool.POOL.get_idle_size()  # connections not given back
            await conn.execute("DELETE FROM chat_history WHERE conversation_id = $1", cid)
            await conn.execute("DELETE FROM conversations WHERE id = $1", cid)
            await conn.close()
            return [r["message"] for r in saved], in_use_after

    saved, in_use = asyncio.run(run())
    assert saved == ["First sentence. "]
    assert in_use == 0
