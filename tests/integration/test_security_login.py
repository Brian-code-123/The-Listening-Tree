import asyncio
import os
import time
import uuid

import httpx
import pytest

from app.db import pool as db_pool
from app.routers import auth as auth_router
from run import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]

JSON = {"accept": "application/json"}


@pytest.fixture
def account():
    email = f"lock_{uuid.uuid4().hex[:10]}@example.com"
    create_user_direct(email)
    yield email
    delete_user_direct(email)


def _run(scenario):
    """Run `scenario(client)` on one event loop against the real app, so
    concurrent requests really are concurrent (TestClient is one-at-a-time)."""

    async def _main():
        await db_pool.create_pool()
        try:
            transport = httpx.ASGITransport(app=app, client=("198.51.100.7", 4000))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await scenario(client)
        finally:
            await db_pool.close_pool()

    return asyncio.run(_main())


def _login(client, email, password, ip=None):
    headers = dict(JSON)
    if ip:
        headers["x-forwarded-for"] = ip
    return client.post("/auth/login", data={"email": email, "password": password}, headers=headers)


def test_parallel_wrong_guesses_cannot_outrun_the_lockout(account):
    async def scenario(client):
        responses = await asyncio.gather(*[_login(client, account, "wrong-%d" % i) for i in range(10)])
        return [r.status_code for r in responses]

    statuses = _run(scenario)
    assert statuses.count(429) == 5  # attempts 6..10 are refused, however they interleave
    assert statuses.count(200) == 5


def test_an_attacker_on_another_address_cannot_lock_the_real_user_out(account, monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY", "1")

    async def scenario(client):
        for i in range(6):
            await _login(client, account, "wrong-%d" % i, ip="203.0.113.50")
        blocked = await _login(client, account, "wrong-again", ip="203.0.113.50")
        real = await _login(client, account, PASSWORD, ip="203.0.113.99")
        return blocked.status_code, real.status_code, real.json()

    blocked, real_status, body = _run(scenario)
    assert blocked == 429
    assert real_status == 200 and body["success"] is True


def test_the_lock_expires_and_one_typo_afterwards_does_not_relock(account, monkeypatch):
    window = 4
    monkeypatch.setattr(auth_router, "LOGIN_FAIL_WINDOW", window)

    async def scenario(client):
        # Counters are fixed windows, so start right after a boundary or the
        # six attempts could straddle two windows and never reach the limit.
        await asyncio.sleep(window - (time.time() % window) + 0.05)
        for i in range(6):
            await _login(client, account, "wrong-%d" % i)
        locked = await _login(client, account, "wrong-x")
        await asyncio.sleep(window - (time.time() % window) + 0.05)
        after = await _login(client, account, "one-typo")
        return locked.status_code, after.status_code

    locked, after = _run(scenario)
    assert locked == 429
    assert after == 200  # an ordinary "wrong password" answer, not another 429


def test_a_successful_login_clears_the_failure_count(account):
    async def scenario(client):
        for i in range(3):
            await _login(client, account, "wrong-%d" % i)
        ok = await _login(client, account, PASSWORD)
        later = [(await _login(client, account, "wrong-%d" % i)).status_code for i in range(5)]
        return ok.status_code, later

    ok, later = _run(scenario)
    assert ok == 200
    assert later == [200] * 5  # a fresh budget of five


def test_unknown_and_known_accounts_get_the_same_wrong_password_answer(account):
    async def scenario(client):
        known = await _login(client, account, "nope")
        unknown = await _login(client, f"nobody_{uuid.uuid4().hex[:8]}@example.com", "nope")
        return known, unknown

    known, unknown = _run(scenario)
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())


def test_an_unknown_email_still_pays_for_one_password_hash(account, monkeypatch):
    calls = []
    real = auth_router.verify_password_async

    async def spy(pw, stored):
        calls.append(stored)
        return await real(pw, stored)

    monkeypatch.setattr(auth_router, "verify_password_async", spy)

    async def scenario(client):
        await _login(client, f"nobody_{uuid.uuid4().hex[:8]}@example.com", "nope")

    _run(scenario)
    assert len(calls) == 1


def test_a_locked_login_does_not_spend_any_hashing(account, monkeypatch):
    async def lock(client):
        for i in range(5):
            await _login(client, account, "wrong-%d" % i)

    _run(lock)
    calls = []
    real = auth_router.verify_password_async

    async def spy(pw, stored):
        calls.append(1)
        return await real(pw, stored)

    monkeypatch.setattr(auth_router, "verify_password_async", spy)

    async def locked(client):
        return await _login(client, account, PASSWORD)

    resp = _run(locked)
    assert resp.status_code == 429
    assert calls == []
