import asyncio
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.background import auto_expire_old_reminders
from app.db import pool as db_pool
from run import app
from tests.integration.helpers import register_and_login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]


def _sql(query: str, *args):
    async def _run():
        conn = await asyncpg.connect(dsn=db_pool.ASYNCPG_DSN, statement_cache_size=0)
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_expiry_job_deactivates_old_one_off_reminders_but_keeps_daily_ones():
    daily, once = f"walk {uuid.uuid4().hex[:6]}", f"pill {uuid.uuid4().hex[:6]}"
    with TestClient(app) as client:
        register_and_login(client)
        client.post("/reminders", data={"label": daily, "time": "08:00", "repeat": "daily"})
        client.post("/reminders", data={"label": once, "time": "09:00"})
        _sql("UPDATE reminders SET created_at = now() - interval '2 days' WHERE label = ANY($1::text[])", [daily, once])

        client.portal.call(auto_expire_old_reminders)  # runs on the app's own event loop / pool

        active = {r["label"]: r["is_active"] for r in _sql("SELECT label, is_active FROM reminders WHERE label = ANY($1::text[])", [daily, once])}
        assert active == {daily: True, once: False}
        listed = {r["label"] for r in client.get("/get_reminders").json()["reminders"]}
        assert daily in listed and once not in listed
