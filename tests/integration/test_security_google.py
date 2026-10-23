import asyncio
import os
import types
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.db import pool as db_pool
from app.services import security_events
from run import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]
JSON_H = {"accept": "application/json"}


@pytest.fixture
def google(monkeypatch):
    """Pretend Google returns whatever the test sets in `claims`."""
    claims = {}

    async def _token(request):
        return {"userinfo": dict(claims)}

    monkeypatch.setattr(config, "GOOGLE_LOGIN_ENABLED", True)
    monkeypatch.setattr(config, "oauth", types.SimpleNamespace(google=types.SimpleNamespace(authorize_access_token=_token)), raising=False)
    return claims


def _sql(sql, *args):
    async def _run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _callback(client):
    return client.get("/auth/google/callback", follow_redirects=False)


def _new_email():
    return f"g_{uuid.uuid4().hex[:10]}@example.com"


def test_linking_an_existing_account_ends_its_older_sessions_but_keeps_the_password(google):
    email = _new_email()
    user_id = create_user_direct(email)
    google.update(sub=f"sub-{uuid.uuid4().hex}", email=email, email_verified=True, name="Ann")
    try:
        with TestClient(app) as client:
            client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON_H)
            old = [c.value for c in client.cookies.jar if c.name == "lt_session"][-1]
            client.cookies.clear()
            resp = _callback(client)
            assert resp.status_code == 303 and resp.headers["location"] == "/"
            assert client.get("/me").status_code == 200
            assert _sql("SELECT session_version, auth_provider FROM users WHERE id = $1", user_id)[0]["session_version"] == 1
            client.cookies.clear()
            client.cookies.set("lt_session", old, domain="testserver.local", path="/")
            assert client.get("/me").status_code == 401  # the session from before the link
            client.cookies.clear()
            # a mailbox owner registered this password; linking Google does not take it away
            assert client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON_H).json()["success"] is True
        events = _sql("SELECT event FROM security_events WHERE user_id = $1", user_id)
        assert "google_link" in [e["event"] for e in events]
    finally:
        _sql("DELETE FROM security_events WHERE user_id = $1", user_id)
        delete_user_direct(email)


def test_an_unverified_google_email_is_refused(google):
    google.update(sub="sub-x", email=_new_email(), email_verified=False)
    with TestClient(app) as client:
        resp = _callback(client)
        assert resp.headers["location"].endswith("error=google_failed")
        assert client.get("/me").status_code == 401


def test_a_disabled_account_cannot_sign_in_with_google(google):
    email = _new_email()
    user_id = create_user_direct(email)
    _sql("UPDATE users SET is_active = FALSE WHERE id = $1", user_id)
    google.update(sub=f"sub-{uuid.uuid4().hex}", email=email, email_verified=True)
    try:
        with TestClient(app) as client:
            resp = _callback(client)
            assert resp.headers["location"].endswith("error=google_failed")
            assert client.get("/me").status_code == 401
    finally:
        delete_user_direct(email)


def test_a_new_google_user_is_created_and_signed_in(google):
    email = _new_email()
    google.update(sub=f"sub-{uuid.uuid4().hex}", email=email, email_verified=True, name="New Person")
    try:
        with TestClient(app) as client:
            assert _callback(client).headers["location"] == "/"
            assert client.get("/me").json()["email"] == email
        row = _sql("SELECT id, auth_provider, password FROM users WHERE LOWER(email) = $1", email)[0]
        assert row["auth_provider"] == "google"
        assert row["password"].startswith("pbkdf2_sha256$")
        events = _sql("SELECT event FROM security_events WHERE user_id = $1", row["id"])
        assert "google_login" in [e["event"] for e in events]
    finally:
        _sql("DELETE FROM security_events WHERE email_hash = $1", security_events.email_hash(email))
        delete_user_direct(email)


def test_an_address_already_tied_to_another_google_identity_is_refused(google):
    email = _new_email()
    create_user_direct(email)
    _sql("UPDATE users SET google_id = 'someone-else' WHERE LOWER(email) = $1", email)
    google.update(sub=f"sub-{uuid.uuid4().hex}", email=email, email_verified=True)
    try:
        with TestClient(app) as client:
            assert _callback(client).headers["location"].endswith("error=google_failed")
    finally:
        delete_user_direct(email)
