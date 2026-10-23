import asyncio
import os
import uuid

import asyncpg
import pytest

from app.db import pool as db_pool

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]


def _fetch(sql: str, *args):
    async def _run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_users_has_session_version_and_consent_columns():
    rows = _fetch(
        "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name IN ('session_version', 'consent_at', 'consent_version')"
    )
    cols = {r["column_name"]: r for r in rows}
    assert set(cols) == {"session_version", "consent_at", "consent_version"}
    assert cols["session_version"]["is_nullable"] == "NO"
    assert cols["session_version"]["column_default"] == "0"
    assert cols["consent_at"]["is_nullable"] == "YES"


def test_security_events_table_exists_with_rls_enabled():
    cols = {r["column_name"] for r in _fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'security_events'"
    )}
    assert {"id", "ts", "event", "user_id", "email_hash", "ip", "ua", "detail"} <= cols
    rls = _fetch("SELECT relrowsecurity FROM pg_class WHERE relname = 'security_events'")
    assert rls and rls[0]["relrowsecurity"] is True


def test_email_uniqueness_ignores_case():
    local = uuid.uuid4().hex[:10]
    lower, mixed = f"{local}@example.com", f"{local.upper()}@Example.com"

    async def _run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            await conn.execute("INSERT INTO users (email, password) VALUES ($1, 'x')", lower)
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute("INSERT INTO users (email, password) VALUES ($1, 'x')", mixed)
        finally:
            await conn.execute("DELETE FROM users WHERE LOWER(email) = $1", lower)
            await conn.close()

    asyncio.run(_run())
