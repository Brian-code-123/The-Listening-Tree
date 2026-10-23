import asyncio
import hashlib
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.db import pool as db_pool
from run import app
from tests.integration.helpers import PASSWORD, create_user_direct, delete_user_direct, register_and_login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]
JSON = {"accept": "application/json"}


def _stored_hash(email: str) -> str:
    async def _get():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetchval("SELECT password FROM users WHERE LOWER(email) = LOWER($1)", email)
        finally:
            await conn.close()

    return asyncio.run(_get())


def _set_hash(email: str, stored: str) -> None:
    async def _set():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            await conn.execute("UPDATE users SET password = $1 WHERE LOWER(email) = LOWER($2)", stored, email)
        finally:
            await conn.close()

    asyncio.run(_set())


def test_an_older_hash_is_upgraded_the_next_time_the_user_signs_in():
    email = f"rehash_{uuid.uuid4().hex[:10]}@example.com"
    create_user_direct(email)
    salt = "ab" * 16
    digest = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), salt.encode(), 390000).hex()
    _set_hash(email, f"pbkdf2_sha256$390000${salt}${digest}")
    try:
        with TestClient(app) as client:
            resp = client.post("/auth/login", data={"email": email, "password": PASSWORD}, headers=JSON)
        assert resp.json()["success"] is True
        assert _stored_hash(email).startswith("pbkdf2_sha256$600000$")
    finally:
        delete_user_direct(email)


@pytest.mark.parametrize("password", ["密碼🔑pässwörd!", "x" * 128])
def test_unusual_passwords_can_sign_in(password):
    email = f"unicode_{uuid.uuid4().hex[:10]}@example.com"
    create_user_direct(email, password)
    try:
        with TestClient(app) as client:
            resp = client.post("/auth/login", data={"email": email, "password": password}, headers=JSON)
        assert resp.status_code == 200 and resp.json()["success"] is True
    finally:
        delete_user_direct(email)


def test_an_oversized_password_is_refused_without_an_error():
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/login", data={"email": "someone@example.com", "password": "x" * 5000}, headers=JSON
        )
    assert resp.status_code == 200
    assert resp.json() == {"success": False, "message": "Invalid email or password"}


def test_changing_the_password_is_rate_limited_per_user():
    with TestClient(app) as client:
        register_and_login(client)
        codes = []
        for _ in range(6):
            r = client.post(
                "/profile/password",
                data={"current_password": "wrong-password", "new_password": "NewPass12345!", "confirm_new_password": "NewPass12345!"},
            )
            codes.append(r.status_code)
    assert codes[:5] == [400] * 5
    assert codes[5] == 429
