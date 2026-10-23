import asyncio
import json
import logging
import os
import re
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.db import pool as db_pool
from app.routers import auth as auth_router
from app.services import security_events
from run import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct, seed_verification_code

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]
JSON_H = {"accept": "application/json"}
SECRET_LOOKING = "Sup3r-Secret-Pass!"


def _events(email_or_user: str | int, event: str | None = None):
    async def _q():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            if isinstance(email_or_user, int):
                rows = await conn.fetch("SELECT * FROM security_events WHERE user_id = $1 ORDER BY id", email_or_user)
            else:
                h = security_events.email_hash(email_or_user)
                rows = await conn.fetch("SELECT * FROM security_events WHERE email_hash = $1 ORDER BY id", h)
            return [dict(r) for r in rows if event is None or r["event"] == event]
        finally:
            await conn.close()

    return asyncio.run(_q())


def _cleanup(email):
    async def _c():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            await conn.execute("DELETE FROM security_events WHERE email_hash = $1", security_events.email_hash(email))
            await conn.execute("DELETE FROM email_verifications WHERE LOWER(email) = LOWER($1)", email)
        finally:
            await conn.close()

    asyncio.run(_c())
    delete_user_direct(email)


@pytest.fixture
def account():
    email = f"evt_{uuid.uuid4().hex[:10]}@example.com"
    user_id = create_user_direct(email)
    yield email, user_id
    _cleanup(email)


def test_failed_and_successful_logins_are_recorded(account):
    email, user_id = account
    with TestClient(app) as client:
        client.post("/auth/login", data={"email": email, "password": "wrong-pass-1"}, headers=JSON_H)
        client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON_H)
    names = [e["event"] for e in _events(email)]
    assert names == ["login_failure", "login_success"]
    success = _events(email, "login_success")[0]
    assert success["user_id"] == user_id
    assert success["ip"] and success["ua"] is not None


def test_a_lockout_is_recorded_once_however_long_the_attack_goes(account):
    email, _ = account
    with TestClient(app) as client:
        for i in range(9):
            client.post("/auth/login", data={"email": email, "password": "wrong-%d" % i}, headers=JSON_H)
    assert len(_events(email, "login_locked")) == 1
    assert len(_events(email, "login_failure")) == 5


def test_password_change_and_code_events_are_recorded(account, monkeypatch):
    email, user_id = account
    monkeypatch.setattr(auth_router, "send_verification_email", lambda *a, **k: True)
    with TestClient(app) as client:
        client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON_H)
        client.post(
            "/profile/password",
            data={"current_password": PASSWORD, "new_password": "BrandNew-12345", "confirm_new_password": "BrandNew-12345"},
        )
    assert len(_events(user_id, "password_change")) == 1

    fresh = f"evt_{uuid.uuid4().hex[:10]}@example.com"
    try:
        with TestClient(app) as client:
            client.post("/send_verification_code", json={"email": fresh}, headers=JSON_H)
            client.post(
                "/auth/register",
                data={"email": fresh, "password": PASSWORD, "confirm_password": PASSWORD, "consent": "true", "verification_code": "000000"},
                headers=JSON_H,
            )
        assert len(_events(fresh, "code_sent")) == 1
        assert len(_events(fresh, "code_failed")) == 1
    finally:
        _cleanup(fresh)


def test_registering_is_recorded(monkeypatch):
    email = f"evt_{uuid.uuid4().hex[:10]}@example.com"
    code = seed_verification_code(email, "314159")
    try:
        with TestClient(app) as client:
            client.post(
                "/auth/register",
                data={"email": email, "password": PASSWORD, "confirm_password": PASSWORD, "consent": "true", "verification_code": code},
                headers=JSON_H,
            )
        assert len(_events(email, "register")) == 1
    finally:
        _cleanup(email)


def test_recording_never_breaks_the_request(monkeypatch):
    async def _down():
        raise RuntimeError("database is down")

    monkeypatch.setattr(security_events.db, "get_db", _down)
    assert asyncio.run(security_events.record_event("login_failure", email="a@example.com")) is None


def test_the_email_hash_is_stable_and_ignores_case():
    assert security_events.email_hash("A@Example.com") == security_events.email_hash(" a@example.COM ")
    assert re.fullmatch(r"[0-9a-f]{64}", security_events.email_hash("a@example.com"))


def test_logs_carry_no_passwords_codes_or_plain_emails(account, caplog):
    email, _ = account
    caplog.set_level(logging.DEBUG)
    with TestClient(app) as client:
        client.post("/auth/login", data={"email": email, "password": SECRET_LOOKING}, headers=JSON_H)
    text = caplog.text
    assert SECRET_LOOKING not in text
    assert email not in text
    assert "login_failure" in text


def test_a_hostile_email_cannot_forge_a_log_line(caplog):
    caplog.set_level(logging.INFO, logger="app.security")
    hostile = 'x@example.com\n{"event":"login_success","user_id":1}'
    asyncio.run(security_events.record_event("login_failure", email=hostile))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[SECURITY_EVENT]")]
    assert len(lines) == 1
    assert "\n" not in lines[0]
    payload = json.loads(lines[0].split(" ", 1)[1])
    assert payload["event"] == "login_failure"


def test_a_device_token_is_not_written_to_the_log(account, caplog):
    email, _ = account
    caplog.set_level(logging.DEBUG)
    with TestClient(app) as client:
        client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON_H)
        resp = client.post("/register_device", json={"device_token": "TOKEN-do-not-log-12345"})
    assert resp.status_code == 200
    assert "TOKEN-do-not-log-12345" not in caplog.text


def test_a_registration_failure_neither_logs_the_email_nor_promises_stored_data(monkeypatch, caplog):
    async def _boom(*args, **kwargs):
        raise RuntimeError("insert failed for victim@example.com")

    email = f"evt_{uuid.uuid4().hex[:10]}@example.com"
    code = seed_verification_code(email, "271828")
    monkeypatch.setattr(auth_router, "_create_user_and_start_session", _boom)
    caplog.set_level(logging.DEBUG)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/auth/register",
                data={"email": email, "password": PASSWORD, "confirm_password": PASSWORD, "consent": "true", "verification_code": code},
                headers=JSON_H,
            )
        assert resp.status_code == 500
        assert "remains in database" not in resp.text and "資料庫" not in resp.text
        assert "victim@example.com" not in caplog.text
        assert "RuntimeError" in caplog.text
    finally:
        _cleanup(email)
