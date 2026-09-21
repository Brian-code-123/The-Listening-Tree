import asyncio
import uuid
from datetime import datetime, timedelta

import asyncpg

from app.db import pool as db_pool

PASSWORD = "TestPass123!"


def new_user_email() -> str:
    return f"integration_{uuid.uuid4().hex[:10]}@example.com"


def seed_verification_code(email: str, code: str = "123456") -> str:
    # Standalone connection: the app pool is bound to TestClient's event loop.
    async def _seed():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        ts = datetime.now()
        await conn.execute(
            "INSERT INTO email_verifications (email, code, expires_at, created_at) VALUES ($1, $2, $3, $4)",
            email, code, ts + timedelta(minutes=10), ts,
        )
        await conn.close()

    asyncio.run(_seed())
    return code


def register_and_login(client) -> tuple[str, str]:
    email = new_user_email()
    code = seed_verification_code(email)
    reg = client.post(
        "/register",
        data={"email": email, "password": PASSWORD, "confirm_password": PASSWORD, "verification_code": code},
        follow_redirects=False,
    )
    assert reg.status_code == 303
    login = client.post("/login", data={"email": email, "password": PASSWORD}, follow_redirects=False)
    assert login.status_code == 303
    # No explicit cookie handling: the client's jar keeps the session cookie and
    # follows later Set-Cookie updates (e.g. /set_language). Pinning it with
    # client.cookies.set() would shadow those updates.
    assert client.cookies.get("lt_session")
    return email, PASSWORD
