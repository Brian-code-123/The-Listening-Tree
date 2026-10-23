import asyncio
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.db import pool as db_pool
from app.main import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct
from tests.integration.test_security_limits import JSON_H, _ask, _signed_in

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1")]


def _sql(sql, *args):
    async def run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(run())


@pytest.fixture
def two_users():
    a, b = (f"acct_{uuid.uuid4().hex[:8]}@example.com" for _ in range(2))
    create_user_direct(a), create_user_direct(b)
    yield a, b
    delete_user_direct(a), delete_user_direct(b)


def _uid(email):
    rows = _sql("SELECT id FROM users WHERE email = $1", email)
    return rows[0]["id"] if rows else None


def test_delete_needs_the_right_password(two_users):
    a, _ = two_users
    with TestClient(app) as client:
        _signed_in(client, a)
        assert client.post("/auth/delete-account", data={"password": "wrong-password"}).status_code == 403
        assert client.post("/auth/delete-account", data={}).status_code == 403
    assert _uid(a) is not None


def test_delete_erases_everything_of_mine_and_nothing_of_anyone_elses(two_users):
    a, b = two_users
    with TestClient(app) as client:
        _signed_in(client, b)
        _ask(client, "hello from b")
        client.post("/reminders", data={"label": "b pill", "time": "09:00"})
        client.cookies.clear()
        _signed_in(client, a)
        _ask(client, "hello from a")
        client.post("/reminders", data={"label": "a pill", "time": "09:00"})
        uid_a, uid_b = _uid(a), _uid(b)
        _sql("INSERT INTO rate_limit_events (key, window_start, count) VALUES ($1, now(), 1), ($2, now(), 1)", f"login_fail:{a.lower()}:1.2.3.4", f"login_fail:{b.lower()}:1.2.3.4")
        assert client.post("/auth/delete-account", data={"password": PASSWORD}).json()["success"] is True
        assert client.get("/me").status_code in (401, 200) and client.get("/me").json().get("authenticated") in (False, None)
    for table in ("chat_history", "conversations", "reminders", "preferences"):
        assert _sql(f"SELECT 1 FROM {table} WHERE user_id = $1", uid_a) == []
    assert _uid(a) is None
    assert _sql("SELECT 1 FROM rate_limit_events WHERE position($1 in key) > 0", a.lower()) == []  # no address left in limiter keys
    assert _sql("SELECT 1 FROM rate_limit_events WHERE position($1 in key) > 0", b.lower())  # someone else's untouched
    _sql("DELETE FROM rate_limit_events WHERE position($1 in key) > 0", b.lower())
    assert _sql("SELECT 1 FROM chat_history WHERE user_id = $1", uid_b)
    assert _sql("SELECT 1 FROM reminders WHERE user_id = $1", uid_b)
    assert _sql("SELECT 1 FROM security_events WHERE event = 'account_deleted' ORDER BY id DESC LIMIT 1")


def test_old_cookie_stops_working_after_deletion(two_users):
    a, _ = two_users
    with TestClient(app) as client:
        _signed_in(client, a)
        saved = dict(client.cookies)
        client.post("/auth/delete-account", data={"password": PASSWORD})
        client.cookies.clear()
        for k, v in saved.items():
            client.cookies.set(k, v, domain="testserver.local", path="/")
        assert client.post("/get_response", data={"msg": "hi"}).status_code == 401


def test_export_is_mine_only_and_has_no_password(two_users):
    a, b = two_users
    with TestClient(app) as client:
        _signed_in(client, b)
        _ask(client, "secret of b")
        client.cookies.clear()
        _signed_in(client, a)
        _ask(client, "words of a")
        resp = client.get("/account/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.text
    assert "words of a" in text and "secret of b" not in text
    body = resp.json()
    assert "password" not in body["profile"] and b not in text


def test_export_needs_a_session():
    with TestClient(app) as client:
        assert client.get("/account/export").status_code == 401


def test_register_needs_consent_and_records_it():
    email = f"cons_{uuid.uuid4().hex[:8]}@example.com"
    from tests.integration.helpers import seed_verification_code

    code = seed_verification_code(email)
    data = {"email": email, "password": PASSWORD, "confirm_password": PASSWORD, "verification_code": code}
    try:
        with TestClient(app) as client:
            r = client.post("/auth/register", data=data, headers=JSON_H)
            assert r.status_code == 400 and r.json()["field"] == "consent"
            assert _uid(email) is None
            r = client.post("/auth/register", data={**data, "consent": "true"}, headers=JSON_H)
            assert r.json()["success"] is True
        row = _sql("SELECT consent_at, consent_version FROM users WHERE email = $1", email)[0]
        assert row["consent_at"] is not None and row["consent_version"] == "2026-10"
    finally:
        delete_user_direct(email)
