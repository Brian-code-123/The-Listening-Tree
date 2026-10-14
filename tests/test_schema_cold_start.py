import asyncio

import pytest

from app.db import schema

# conftest.py's autouse fixture swaps schema.ensure_db_initialized for a fake at
# test time; grab the real one at import time, before any fixture runs.
real_ensure_db_initialized = schema.ensure_db_initialized


class _FakeCursor:
    def __init__(self, stamped: bool, missing_table: bool):
        self._stamped = stamped
        self._missing_table = missing_table

    async def execute(self, query, params=()):
        if self._missing_table:
            raise RuntimeError('relation "alembic_version" does not exist')

    def fetchone(self):
        return (1,) if self._stamped else None


class _FakeConn:
    def __init__(self, stamped: bool, missing_table: bool = False):
        self.cur = _FakeCursor(stamped, missing_table)
        self.closed = False

    def cursor(self):
        return self.cur

    async def close(self):
        self.closed = True


@pytest.fixture
def init_db_calls(monkeypatch):
    calls = []

    async def _fake_init_db():
        calls.append(1)

    monkeypatch.setattr(schema, "init_db", _fake_init_db)
    monkeypatch.setattr(schema, "_db_initialized", False)
    monkeypatch.setattr(schema, "_db_init_error", None)
    return calls


def _run(conn):
    async def _get_db():
        return conn

    return _get_db


def test_alembic_stamped_database_skips_the_ddl_bootstrap(monkeypatch, init_db_calls):
    conn = _FakeConn(stamped=True)
    monkeypatch.setattr(schema.db, "get_db", _run(conn))

    assert asyncio.run(real_ensure_db_initialized()) is True
    assert init_db_calls == []
    assert conn.closed


@pytest.mark.parametrize("conn", [
    _FakeConn(stamped=False),                      # table exists but empty
    _FakeConn(stamped=False, missing_table=True),  # brand-new database
])
def test_unstamped_database_still_gets_the_ddl_bootstrap(monkeypatch, init_db_calls, conn):
    monkeypatch.setattr(schema.db, "get_db", _run(conn))

    assert asyncio.run(real_ensure_db_initialized()) is True
    assert init_db_calls == [1]
    assert conn.closed
