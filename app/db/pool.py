"""asyncpg connection pool: DSN resolution, pool lifecycle.

`POOL` is deliberately a *module attribute*, not something re-exported via
`from app.db.pool import POOL` elsewhere — callers do `from app.db import
pool` and read `pool.POOL`, so `create_pool()`/`close_pool()` reassigning it
here is visible everywhere without needing a `global` across module
boundaries (which doesn't work) or a mutable-container workaround.
"""
import os
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    import asyncpg
except ImportError:
    asyncpg = None

if asyncpg is None:
    raise RuntimeError("asyncpg is required for PostgreSQL connection but is not installed.")


def _normalize_db_url(raw_url: str) -> str:
    """Ensure required DB URL query params exist for production-safe connections."""
    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    query_string = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query_string, parts.fragment))


_POOLER_DATABASE_URL = (
    os.environ.get("SUPABASE_POOLER_URL")
    or os.environ.get("POSTGRES_POOLER_URL")
    or os.environ.get("DATABASE_POOLER_URL")
)
_DATABASE_URL = _POOLER_DATABASE_URL or os.environ.get("DATABASE_URL")
if not _DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Configure Supabase PostgreSQL URL in environment variables."
    )

DB_BACKEND = "postgres"
DB_URL_SOURCE = "pooler_url" if _POOLER_DATABASE_URL else "database_url"
RUNTIME_DB_BACKEND = DB_BACKEND
LAST_PG_ATTEMPTS: List[str] = []  # kept for /health/db's JSON shape; asyncpg's pool retries internally

# asyncpg parses `sslmode` straight out of the DSN itself (same as libpq) —
# do NOT also pass an explicit `ssl=` kwarg to connect()/create_pool(): an
# explicit kwarg overrides the DSN and forces asyncpg's negotiated-TLS path,
# which hangs indefinitely against Supabase's pooler (Supavisor) — a known
# asyncpg/Supavisor incompatibility, unrelated to any code here. Confirmed by
# testing ssl=True, ssl="require", and a manual ssl.SSLContext — all hang;
# ssl=None (DSN-driven) connects in <0.3s. Respecting whatever `sslmode` the
# DSN already carries (disable locally via .env.local, require in production
# via .env) is both the fix and the correct behavior — it's exactly what
# psycopg2 already did here.
ASYNCPG_DSN = _normalize_db_url(_DATABASE_URL)
DB_HOSTNAME = urlsplit(ASYNCPG_DSN).hostname
DB_HOSTADDR = None  # asyncpg resolves the host itself; no manual IP pinning needed
DB_RUNTIME_LABEL = "asyncpg-pool"

POOL: Optional["asyncpg.Pool"] = None


async def create_pool() -> "asyncpg.Pool":
    """Create the process-wide asyncpg pool and store it on this module."""
    global POOL
    POOL = await asyncpg.create_pool(
        dsn=ASYNCPG_DSN,  # sslmode is read from the DSN itself — see ASYNCPG_DSN's comment
        # min_size=0: connections open lazily on first use instead of the
        # pool eagerly dialing Postgres at creation time. Keeps app startup
        # (and CI, which monkeypatches get_db() but not pool creation) from
        # requiring a reachable database just to construct the pool object.
        min_size=0,
        max_size=10,
        statement_cache_size=0,  # required behind Supabase's transaction-pooling PgBouncer
        command_timeout=15,       # bounds a stuck query instead of freezing the whole server
        # The background task only touches the DB once every 60s — well past
        # Supabase's pooler-side idle timeout, which was closing the
        # connection server-side while asyncpg's pool still thought it was
        # good, surfacing as "connection was closed in the middle of
        # operation" on the next use. Recycle idle connections client-side
        # before that can happen.
        max_inactive_connection_lifetime=30,
    )
    return POOL


async def close_pool() -> None:
    global POOL
    if POOL is not None:
        await POOL.close()
        POOL = None
