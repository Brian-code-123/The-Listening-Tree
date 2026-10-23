import asyncio
import base64
import json
import os
import time
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.core import config, session_guard
from app.db import pool as db_pool
from run import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]
JSON_H = {"accept": "application/json"}


def _sign(data: dict) -> str:
    signer = TimestampSigner(str(config.SECRET_KEY))
    return signer.sign(base64.b64encode(json.dumps(data).encode())).decode()


def _read(cookie: str) -> dict:
    return json.loads(base64.b64decode(TimestampSigner(str(config.SECRET_KEY)).unsign(cookie.encode())))


def _sql(sql: str, *args):
    async def _run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.fixture
def account():
    email = f"sess_{uuid.uuid4().hex[:10]}@example.com"
    user_id = create_user_direct(email)
    yield email, user_id
    delete_user_direct(email)


def _login(client, email, remember=False):
    data = {"email": email, "password": PASSWORD}
    if remember:
        data["remember_me"] = "on"
    resp = client.post("/auth/login", data=data, headers=JSON_H)
    assert resp.json()["success"] is True
    return client.cookies.get("lt_session")


def _as(client, cookie: str | None):
    """/me as a browser holding exactly this cookie. One TestClient is used for
    everything (the app has a single global DB pool), so jars are swapped."""
    saved = list(client.cookies.jar)
    client.cookies.clear()
    if cookie:
        client.cookies.set("lt_session", cookie)
    try:
        return client.get("/me")
    finally:
        client.cookies.clear()
        for c in saved:
            client.cookies.jar.set_cookie(c)


def test_logging_out_kills_a_copied_cookie(account):
    email, _ = account
    with TestClient(app) as client:
        cookie = _login(client, email)
        assert _as(client, cookie).status_code == 200
        out = client.post("/auth/logout", headers=JSON_H)
        assert out.status_code == 200 and out.json()["success"] is True
        assert _as(client, cookie).status_code == 401


def test_changing_the_password_kills_other_sessions(account):
    email, _ = account
    with TestClient(app) as client:
        stolen = _login(client, email)
        client.cookies.clear()
        _login(client, email)  # the "phone"
        resp = client.post(
            "/profile/password",
            data={"current_password": PASSWORD, "new_password": "BrandNew-12345", "confirm_new_password": "BrandNew-12345"},
        )
        assert resp.json()["success"] is True
        # the phone just changed it, so it must stay signed in
        assert client.get("/me").status_code == 200
        assert _as(client, stolen).status_code == 401


def test_a_cookie_issued_before_this_change_still_works(account):
    email, user_id = account
    legacy = _sign({"user_id": user_id, "user_email": email, "remember_me": True, "language": "en"})
    with TestClient(app) as client:
        assert _as(client, legacy).status_code == 200


def test_a_removed_or_disabled_user_loses_the_session(account):
    email, user_id = account
    with TestClient(app) as client:
        cookie = _login(client, email)
        _sql("UPDATE users SET is_active = FALSE WHERE id = $1", user_id)
        assert _as(client, cookie).status_code == 401
        _sql("UPDATE users SET is_active = TRUE WHERE id = $1", user_id)
        assert _as(client, cookie).status_code == 200
        delete_user_direct(email)
        assert _as(client, cookie).status_code == 401


def test_a_browser_session_login_expires_on_the_server_too(account):
    email, user_id = account
    with TestClient(app) as client:
        cookie = _login(client, email, remember=False)
    data = _read(cookie)
    assert data["user_id"] == user_id and data["sv"] == 0
    assert 11 * 3600 < data["exp"] - time.time() <= 12 * 3600 + 5
    expired = _sign({**data, "exp": time.time() - 1})
    with TestClient(app) as client:
        assert _as(client, expired).status_code == 401


def test_remember_me_has_no_server_side_expiry(account):
    email, _ = account
    with TestClient(app) as client:
        cookie = _login(client, email, remember=True)
    assert "exp" not in _read(cookie)


def test_login_starts_a_fresh_session_but_keeps_the_language(account):
    email, _ = account
    stale = _sign({"language": "zh-HK", "stale_game_state": {"answer": 42}})
    with TestClient(app) as client:
        client.cookies.set("lt_session", stale, domain="testserver.local", path="/")
        cookie = _login(client, email)
    data = _read(cookie)
    assert "stale_game_state" not in data
    assert data["language"] == "zh-HK"


def test_logout_by_get_is_not_allowed_any_more(account):
    email, _ = account
    with TestClient(app) as client:
        cookie = _login(client, email)
        assert client.get("/logout", follow_redirects=False).status_code == 405
        assert client.get("/auth/logout", follow_redirects=False).status_code == 405
        assert _as(client, cookie).status_code == 200


def test_logout_keeps_the_language_for_the_login_page(account):
    email, _ = account
    with TestClient(app) as client:
        client.get("/set_language/zh-HK", follow_redirects=False)
        _login(client, email)
        client.post("/auth/logout", headers=JSON_H)
        assert client.get("/me").json()["lang"] == "zh-HK"


def test_static_files_do_not_cost_a_database_lookup(account, monkeypatch):
    email, _ = account
    calls = []
    real = session_guard._load_state

    async def spy(user_id):
        calls.append(user_id)
        return await real(user_id)

    with TestClient(app) as client:
        _login(client, email)
        monkeypatch.setattr(session_guard, "_load_state", spy)
        assert client.get("/static/style.css").status_code == 200
        assert calls == []
        client.get("/me")
        assert len(calls) == 1


def test_a_failing_lookup_lets_the_request_through(account, monkeypatch):
    email, _ = account

    async def down(user_id):
        raise RuntimeError("database hiccup")

    with TestClient(app) as client:
        _login(client, email)
        monkeypatch.setattr(session_guard, "_load_state", down)
        assert client.get("/me").status_code == 200
