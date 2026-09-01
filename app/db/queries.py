"""psycopg2-shaped adapter around one asyncpg pool.

Callers should `from app.db import queries as db` and call `db.get_db()`,
`db.db_execute(...)`, etc. — NOT `from app.db.queries import get_db` — so
that tests monkeypatching `queries.get_db` (see tests/conftest.py) affect
every call site. A `from X import Y` binding is copied into the importing
module's namespace at import time and does not see a later monkeypatch of
the origin module's attribute.
"""
from datetime import datetime
from typing import Optional

from app.db import pool as _pool

try:
    import asyncpg
    PgIntegrityError = asyncpg.exceptions.IntegrityConstraintViolationError
    PgInterfaceError = asyncpg.exceptions.InterfaceError
except ImportError:
    asyncpg = None
    class PgIntegrityError(Exception):
        pass
    class PgInterfaceError(Exception):
        pass


def _safe_rowcount(cursor) -> int:
    """Return cursor rowcount if available; otherwise fall back to 0.

    Some DB-API implementations and test fakes do not expose ``rowcount``.
    """
    rc = getattr(cursor, "rowcount", None)
    if isinstance(rc, int) and rc >= 0:
        return rc
    return 0


def _json_timestamp(value) -> str:
    """Normalize timestamp-like values into JSON-safe strings."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if value is None:
        return ""
    return str(value)


def _to_dollar_placeholders(query: str) -> str:
    """Convert `?` or `%s` positional placeholders to asyncpg's `$1, $2, ...`."""
    out = []
    n = 0
    i = 0
    length = len(query)
    while i < length:
        ch = query[i]
        if ch == "?":
            n += 1
            out.append(f"${n}")
            i += 1
        elif ch == "%" and i + 1 < length and query[i + 1] == "s":
            n += 1
            out.append(f"${n}")
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse_status_rowcount(status: str) -> int:
    """Parse the trailing row count out of an asyncpg command-complete tag
    (e.g. "UPDATE 3" -> 3, "INSERT 0 1" -> 1, "CREATE TABLE" -> 0)."""
    if not status:
        return 0
    last = status.split()[-1]
    return int(last) if last.isdigit() else 0


import re as _re
_DATE_STRING_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_STRING_RE = _re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _coerce_param_for_asyncpg(value):
    """Convert a `strftime('%Y-%m-%d[ %H:%M:%S]')`-formatted string into a real
    `date`/`datetime` object.

    Every DATE/TIMESTAMP value in this codebase is passed around as a
    pre-formatted string (matching what psycopg2 accepted — it sends every
    parameter as text and lets Postgres cast it). asyncpg's typed binary
    protocol does not: once a query infers a parameter's column type as
    date/timestamp, it requires an actual Python `date`/`datetime` object and
    raises on a plain string. Rather than hand-converting dozens of call
    sites, coerce transparently here — every date/timestamp *column* in this
    schema is always fed a string in exactly one of these two formats, so
    the match is unambiguous in practice.
    """
    if isinstance(value, str):
        if _DATETIME_STRING_RE.match(value):
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        if _DATE_STRING_RE.match(value):
            return datetime.strptime(value, "%Y-%m-%d").date()
    return value


class _CursorShim:
    """Minimal psycopg2-cursor-shaped wrapper around one asyncpg connection,
    so the ~45 existing call sites (`db_execute(c, query, params)` then
    `c.fetchall()`/`c.fetchone()`) keep working almost unchanged."""

    __slots__ = ("_conn_shim", "_rows", "rowcount")

    def __init__(self, conn_shim: "_ConnShim"):
        self._conn_shim = conn_shim
        self._rows: list = []
        self.rowcount = 0

    async def execute(self, query: str, params: tuple = ()) -> None:
        await self._conn_shim._ensure_tx()
        pg_query = _to_dollar_placeholders(query)
        params = tuple(_coerce_param_for_asyncpg(p) for p in params)
        if pg_query.strip().upper().startswith("SELECT") or "RETURNING" in pg_query.upper():
            self._rows = await self._conn_shim._raw.fetch(pg_query, *params)
            self.rowcount = len(self._rows)
        else:
            status = await self._conn_shim._raw.execute(pg_query, *params)
            self._rows = []
            self.rowcount = _parse_status_rowcount(status)

    def fetchall(self) -> list:
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _ConnShim:
    """Mimics the psycopg2 connection this codebase's ~45 call sites already
    use (`conn.cursor()`, `conn.commit()`, `conn.close()`), backed by one
    asyncpg.Connection acquired from the pool.

    Wraps every acquired connection in an explicit transaction on first use,
    matching psycopg2's default (autocommit=False) behaviour: statements
    only become durable on `commit()`, and `close()` without a prior
    `commit()` rolls back — asyncpg itself is autocommit-per-statement
    unless a transaction is explicitly started.
    """

    __slots__ = ("_raw", "_in_tx")

    def __init__(self, raw: "asyncpg.Connection"):
        self._raw = raw
        self._in_tx = False

    async def _ensure_tx(self) -> None:
        # Plain SQL BEGIN, not asyncpg's `Transaction` helper object — that
        # helper tracks its own client-side state and raises "cannot
        # rollback; the transaction is in error state" once a query inside
        # it fails, instead of letting a plain ROLLBACK clear the aborted
        # transaction (which Postgres always accepts, error state or not).
        if not self._in_tx:
            await self._raw.execute("BEGIN")
            self._in_tx = True

    def cursor(self) -> _CursorShim:
        return _CursorShim(self)

    async def commit(self) -> None:
        if self._in_tx:
            await self._raw.execute("COMMIT")
            self._in_tx = False

    async def close(self) -> None:
        if self._in_tx:
            try:
                await self._raw.execute("ROLLBACK")
            except Exception:
                pass  # connection is unusable either way — discard it below
            self._in_tx = False
        await _pool.POOL.release(self._raw)


async def get_db() -> _ConnShim:
    """Acquire a connection from the pool, wrapped to look like a psycopg2
    connection. Callers must still call `await conn.close()` when done,
    which releases it back to the pool."""
    raw = await _pool.POOL.acquire()
    return _ConnShim(raw)


async def db_execute(cursor: _CursorShim, query: str, params: tuple = ()) -> None:
    """Execute a query using the existing `?`-style placeholder convention."""
    await cursor.execute(query, params)


async def db_insert_or_replace_preference(cursor: _CursorShim, user_id: int, key: str, value: str, ts: str) -> None:
    """Insert or update user preference using PostgreSQL UPSERT syntax."""
    await cursor.execute(
        """
        INSERT INTO preferences (user_id, pref_key, pref_value, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (user_id, pref_key)
        DO UPDATE SET pref_value = EXCLUDED.pref_value, updated_at = EXCLUDED.updated_at
        """,
        (user_id, key, value, ts),
    )
