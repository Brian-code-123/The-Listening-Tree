"""DB-backed rate limiting: per-key sliding-bucket counter stored in Postgres.

Not `slowapi` with its default in-memory storage — this app's production
runtime is Vercel serverless (api/index.py), where separate function
instances have independent memory, so an in-process counter doesn't
actually enforce a shared limit across them. Postgres is already this app's
real shared state (same DB every instance talks to), so it's the counter
store too — the same idea as the existing `failed_login_attempts`/
`locked_until` account-lockout columns on `users`, generalized.

The increment is a single atomic SQL statement, not "SELECT count then
UPDATE if under limit" — a read-then-write here would let two concurrent
requests both read count=N-1, both decide they're under the limit, and both
proceed, silently letting the true count exceed the limit. See
check_and_increment()'s query.
"""
import ipaddress
import os
from datetime import datetime, timedelta, timezone

from app.db import queries as db


class RateLimitUnavailable(Exception):
    """The counter store could not be reached.

    Raised instead of letting the request through: failing open would give an
    attacker unlimited guesses whenever the database hiccups.
    """


async def hit(key: str, window_seconds: int) -> int:
    """Atomically record one request under `key` in the current fixed window
    and return the count in that window, this request included.

    `window_start` buckets time into fixed windows of `window_seconds`
    (e.g. a 60s window means every request between :00 and :59 of a minute
    shares one bucket) — simpler and cheap-to-clean-up than a true sliding
    window, and generous-enough limits make the fixed-window edge effect
    (up to ~2x limit right at a window boundary) a non-issue here.
    """
    now = datetime.now(timezone.utc)
    bucket_seconds = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(bucket_seconds, tz=timezone.utc)

    try:
        conn = await db.get_db()
        try:
            c = conn.cursor()
            await c.execute(
                """
                INSERT INTO rate_limit_events (key, window_start, count)
                VALUES (?, ?, 1)
                ON CONFLICT (key, window_start)
                DO UPDATE SET count = rate_limit_events.count + 1
                RETURNING count
                """,
                (key, window_start),
            )
            row = c.fetchone()
            await conn.commit()
        finally:
            await conn.close()
    except Exception as e:
        raise RateLimitUnavailable() from e

    return row["count"] if row else 1


async def check_and_increment(key: str, limit: int, window_seconds: int) -> bool:
    """True if this request is within `limit` for the current window, False if
    it should be refused (429). See `hit` for how the count is kept."""
    return await hit(key, window_seconds) <= limit


_MAX_IP_TEXT = 45  # longest valid textual IPv6 address


def _parse_ip(value: str | None):
    value = (value or "").strip()
    if not value or len(value) > _MAX_IP_TEXT:
        return None
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _normalize(ip) -> str:
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        # One household or host usually owns a whole /64, so a /64 is the unit
        # an attacker can rotate within for free.
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def client_ip(request) -> str:
    """The address a request should be limited under.

    X-Forwarded-For is only believed where something we trust sets it: Vercel
    overwrites it (it never forwards a client-supplied value), and TRUSTED_PROXY
    declares any other proxy. Elsewhere a client could send a fresh fake value
    on every request and walk around every limit, so the socket address is used.
    Anything that does not parse as an IP is ignored.
    """
    candidate = None
    if os.environ.get("VERCEL") or os.environ.get("TRUSTED_PROXY"):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            candidate = _parse_ip(forwarded.split(",")[0])
    if candidate is None and request.client:
        candidate = _parse_ip(request.client.host)
    return _normalize(candidate) if candidate else "unknown"


def client_key(request, bucket: str) -> str:
    """Build a rate-limit key from the request's client IP and a bucket
    name (e.g. "login", "register") so different routes don't share limits."""
    return f"{bucket}:{client_ip(request)}"


async def reset_key(key: str) -> None:
    """Forget every window recorded under `key` (e.g. after a successful login)."""
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await c.execute("DELETE FROM rate_limit_events WHERE key = ?", (key,))
        await conn.commit()
    finally:
        await conn.close()


async def cleanup_old_rate_limit_events(older_than_seconds: int = 3600) -> int:
    """Delete rate-limit rows older than `older_than_seconds`. Called from
    app/background.py's periodic loop (skipped on Vercel, same as the rest
    of that loop — stale rows are inert, not a correctness problem, just a
    slow storage-size creep worth revisiting only if it ever becomes
    noticeable)."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await c.execute("DELETE FROM rate_limit_events WHERE window_start < ?", (cutoff,))
        deleted = db._safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    return deleted
