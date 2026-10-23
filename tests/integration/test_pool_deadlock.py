"""More simultaneous requests than the connection pool has connections must
all finish. A request that holds one connection while asking for a second makes
the pool deadlock as soon as every connection is held by such a request."""
import asyncio
import os
import uuid

import httpx
import pytest

from app.main import app
from app.routers import auth as auth_router
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1")]

POOL = 3
CALLERS = 12  # four times the pool


@pytest.fixture
def small_pool(monkeypatch):
    monkeypatch.setenv("DB_POOL_MAX", str(POOL))
    monkeypatch.setattr(auth_router, "LOGIN_RATE_LIMIT", 10_000)


def test_simultaneous_logins_beyond_the_pool_size_all_finish(small_pool):
    emails = [f"pool_{uuid.uuid4().hex[:8]}@example.com" for _ in range(CALLERS)]
    for e in emails:
        create_user_direct(e)

    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                async def login(e):
                    r = await client.post("/auth/login", data={"email": e, "password": PASSWORD}, headers={"accept": "application/json"})
                    return r.status_code, r.json().get("success")

                return await asyncio.wait_for(asyncio.gather(*(login(e) for e in emails)), timeout=40)

    try:
        results = asyncio.run(run())
    finally:
        for e in emails:
            delete_user_direct(e)
    assert results == [(200, True)] * CALLERS


def test_simultaneous_chat_commands_and_registrations_beyond_the_pool_size_all_finish(small_pool, monkeypatch):
    from app.routers import chat as chat_router
    from tests.integration.helpers import seed_verification_code

    async def no_model(*args, **kwargs):
        return "fine"

    monkeypatch.setattr(chat_router, "call_ai", no_model)
    monkeypatch.setattr(auth_router, "REGISTER_RATE_LIMIT", 10_000)
    chatters = [f"poolc_{uuid.uuid4().hex[:8]}@example.com" for _ in range(CALLERS)]
    newcomers = [f"pooln_{uuid.uuid4().hex[:8]}@example.com" for _ in range(CALLERS)]
    for e in chatters:
        create_user_direct(e)
    codes = {e: seed_verification_code(e) for e in newcomers}

    async def run():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)

            async def chat(email, text):
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    await client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers={"accept": "application/json"})
                    r = await client.post("/get_response", data={"msg": text})
                    return r.status_code

            async def register(email):
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    r = await client.post(
                        "/auth/register",
                        data={"email": email, "password": PASSWORD, "confirm_password": PASSWORD, "verification_code": codes[email], "consent": "true"},
                        headers={"accept": "application/json"},
                    )
                    return r.status_code, r.json().get("success")

            jobs = [chat(e, "我想死" if i % 3 == 0 else "set reminder pill 09:00" if i % 3 == 1 else "hello") for i, e in enumerate(chatters)]
            jobs += [register(e) for e in newcomers]
            return await asyncio.wait_for(asyncio.gather(*jobs), timeout=60)

    try:
        results = asyncio.run(run())
    finally:
        for e in chatters + newcomers:
            delete_user_direct(e)
    assert results[:CALLERS] == [200] * CALLERS
    assert results[CALLERS:] == [(200, True)] * CALLERS
