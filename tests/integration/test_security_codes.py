import asyncio
import os
import re
import uuid

import asyncpg
import httpx
import pytest

from app.db import pool as db_pool
from app.routers import auth as auth_router
from run import app
from tests.integration.helpers import PASSWORD, seed_verification_code

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]
JSON = {"accept": "application/json"}


@pytest.fixture
def mail(monkeypatch):
    sent = []
    monkeypatch.setattr(auth_router, "send_verification_email", lambda to, code, lang="en": sent.append((to, code)) or True)
    return sent


def _email():
    return f"code_{uuid.uuid4().hex[:10]}@example.com"


def _run(scenario):
    async def _main():
        await db_pool.create_pool()
        try:
            transport = httpx.ASGITransport(app=app, client=("198.51.100.8", 4000))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await scenario(client)
        finally:
            await db_pool.close_pool()

    return asyncio.run(_main())


def _rows(sql, *args):
    async def _q():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_q())


def _cleanup(email):
    async def _c():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            await conn.execute("DELETE FROM email_verifications WHERE LOWER(email) = LOWER($1)", email)
            await conn.execute("DELETE FROM users WHERE LOWER(email) = LOWER($1)", email)
        finally:
            await conn.close()

    asyncio.run(_c())


def _register(client, email, code, password=PASSWORD):
    return client.post(
        "/auth/register",
        data={"email": email, "password": password, "confirm_password": password, "consent": "true", "verification_code": code},
        headers=JSON,
    )


def _send(client, email):
    return client.post("/send_verification_code", json={"email": email}, headers=JSON)


def test_guessing_stops_after_five_wrong_codes_even_if_the_next_one_is_right():
    email = _email()
    good = seed_verification_code(email, "424242")
    try:
        async def scenario(client):
            wrong = [(await _register(client, email, "00000%d" % i)).status_code for i in range(5)]
            right = await _register(client, email, good)
            return wrong, right.status_code

        wrong, right = _run(scenario)
        assert wrong == [400] * 5
        assert right == 429
    finally:
        _cleanup(email)


def test_a_new_code_retires_the_older_unused_ones(mail):
    email = _email()
    seed_verification_code(email, "111111")
    try:
        _run(lambda client: _send(client, email))
        used = _rows("SELECT used FROM email_verifications WHERE LOWER(email) = LOWER($1) ORDER BY id", email)
        assert [r["used"] for r in used] == [True, False]
    finally:
        _cleanup(email)


def test_parallel_requests_for_one_address_send_exactly_one_code(mail):
    email = _email()
    try:
        async def scenario(client):
            return [r.status_code for r in await asyncio.gather(*[_send(client, email) for _ in range(5)])]

        statuses = _run(scenario)
        assert statuses.count(200) == 1
        assert statuses.count(429) == 4
        assert len(mail) == 1
    finally:
        _cleanup(email)


def test_there_is_a_daily_cap_per_address(mail, monkeypatch):
    monkeypatch.setattr(auth_router, "SEND_CODE_EMAIL_LIMIT", 100)
    monkeypatch.setattr(auth_router, "SEND_CODE_DAY_LIMIT", 3)
    email = _email()
    try:
        async def scenario(client):
            return [(await _send(client, email)).status_code for _ in range(4)]

        assert _run(scenario) == [200, 200, 200, 429]
    finally:
        _cleanup(email)


def test_the_code_is_not_stored_in_the_clear(mail):
    email = _email()
    try:
        _run(lambda client: _send(client, email))
        sent_code = mail[0][1]
        stored = _rows("SELECT code FROM email_verifications WHERE LOWER(email) = LOWER($1)", email)[0]["code"]
        assert not re.fullmatch(r"\d{6}", stored)
        assert re.fullmatch(r"[0-9a-f]{64}", stored)
        assert stored != sent_code
    finally:
        _cleanup(email)


def test_a_registered_address_gets_the_same_answer_and_no_email(mail):
    email = _email()
    taken = _email()
    code = seed_verification_code(taken, "135790")
    try:
        async def scenario(client):
            assert (await _register(client, taken, code)).json()["success"] is True
            client.cookies.clear()
            fresh = await _send(client, email)
            # a second address in a fresh rate-limit bucket so only existence differs
            existing = await _send(client, taken)
            return fresh, existing

        fresh, existing = _run(scenario)
        assert (existing.status_code, existing.json()) == (fresh.status_code, fresh.json())
        assert [to for to, _ in mail] == [email]
    finally:
        _cleanup(email)
        _cleanup(taken)


def test_a_mixed_case_address_registers_with_its_lowercase_code(mail):
    local = uuid.uuid4().hex[:10]
    email = f"{local}@example.com"
    code = seed_verification_code(email, "246810")
    try:
        async def scenario(client):
            return await _register(client, f"{local.upper()}@Example.com", code)

        assert _run(scenario).json()["success"] is True
    finally:
        _cleanup(email)


@pytest.mark.parametrize("kind", ["expired", "used"])
def test_an_expired_or_used_code_is_refused(kind):
    email = _email()
    code = seed_verification_code(email, "975310", expires_in_minutes=-1 if kind == "expired" else 10, used=kind == "used")
    try:
        resp = _run(lambda client: _register(client, email, code))
        assert resp.status_code == 400
        assert resp.json()["field"] == "verification_code"
    finally:
        _cleanup(email)
