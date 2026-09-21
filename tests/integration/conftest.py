import asyncio
import os

import asyncpg
import pytest

from app.db import pool as db_pool


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Registration is limited to 5/min per IP and every test registers a user
    from the same TestClient address, so clear the counters before each test.
    Only under RUN_LIVE_DB=1, where tests/conftest.py has already refused any
    non-local database; otherwise the DB is faked and there is nothing to clear."""
    if os.environ.get("RUN_LIVE_DB") == "1":
        async def _clear():
            conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
            await conn.execute("DELETE FROM rate_limit_events")
            await conn.close()

        asyncio.run(_clear())
    yield
