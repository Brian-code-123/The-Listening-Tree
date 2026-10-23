import asyncio
import os

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.db import pool as db_pool
from app.main import app
from tests.integration.test_security_limits import user  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1")]


def _sql(sql, *args, fetch=False):
    async def run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await (conn.fetch if fetch else conn.execute)(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(run())


def test_needs_the_cron_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value")
    with TestClient(app) as client:
        assert client.get("/internal/cron/cleanup").status_code == 401
        assert client.get("/internal/cron/cleanup", headers={"authorization": "Bearer nope"}).status_code == 401
    monkeypatch.delenv("CRON_SECRET")
    with TestClient(app) as client:
        assert client.get("/internal/cron/cleanup", headers={"authorization": "Bearer "}).status_code == 401


def test_cleanup_purges_only_what_is_old_and_is_idempotent(monkeypatch, user):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value")
    uid = _sql("SELECT id FROM users WHERE email = $1", user, fetch=True)[0]["id"]
    old = _sql("INSERT INTO conversations (user_id, is_deleted, updated_at) VALUES ($1, TRUE, NOW() - INTERVAL '40 days') RETURNING id", uid, fetch=True)[0]["id"]
    new = _sql("INSERT INTO conversations (user_id, is_deleted, updated_at) VALUES ($1, TRUE, NOW() - INTERVAL '2 days') RETURNING id", uid, fetch=True)[0]["id"]
    _sql("INSERT INTO chat_history (user_id, is_bot, message, is_deleted, conversation_id) VALUES ($1, FALSE, 'x', TRUE, $2)", uid, old)
    _sql("INSERT INTO chat_history (user_id, is_bot, message, is_deleted, conversation_id) VALUES ($1, FALSE, 'y', TRUE, $2)", uid, new)
    _sql("INSERT INTO email_verifications (email, code, expires_at, used) VALUES ('old@example.com', 'c', NOW() - INTERVAL '3 days', FALSE)")
    _sql("INSERT INTO email_verifications (email, code, expires_at, used) VALUES ('fresh@example.com', 'c', NOW() + INTERVAL '10 minutes', FALSE)")
    _sql("INSERT INTO security_events (event, ts) VALUES ('t_old', NOW() - INTERVAL '200 days'), ('t_new', NOW())")
    headers = {"authorization": "Bearer s3cret-value"}
    try:
        with TestClient(app) as client:
            first = client.get("/internal/cron/cleanup", headers=headers)
            second = client.get("/internal/cron/cleanup", headers=headers)
        assert first.status_code == 200 and first.json()["ok"] is True
        assert second.status_code == 200
        ids = {r["id"] for r in _sql("SELECT id FROM conversations WHERE user_id = $1", uid, fetch=True)}
        assert old not in ids and new in ids
        assert _sql("SELECT 1 FROM chat_history WHERE conversation_id = $1", old, fetch=True) == []
        assert _sql("SELECT 1 FROM chat_history WHERE conversation_id = $1", new, fetch=True) != []
        assert _sql("SELECT 1 FROM email_verifications WHERE email = 'old@example.com'", fetch=True) == []
        assert _sql("SELECT 1 FROM email_verifications WHERE email = 'fresh@example.com'", fetch=True) != []
        events = {r["event"] for r in _sql("SELECT event FROM security_events WHERE event IN ('t_old','t_new')", fetch=True)}
        assert events == {"t_new"}
    finally:
        _sql("DELETE FROM email_verifications WHERE email IN ('old@example.com','fresh@example.com')")
        _sql("DELETE FROM security_events WHERE event IN ('t_old','t_new')")
        _sql("DELETE FROM chat_history WHERE user_id = $1", uid)
        _sql("DELETE FROM conversations WHERE user_id = $1", uid)
