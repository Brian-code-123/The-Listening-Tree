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
from datetime import datetime, timedelta, timezone

from app.db import queries as db


async def check_and_increment(key: str, limit: int, window_seconds: int) -> bool:
    """Atomically record one request under `key` and report whether it's
    still within `limit` for the current fixed window.

    Returns True if the request is allowed (count <= limit after this
    increment), False if it should be rejected (429).

    `window_start` buckets time into fixed windows of `window_seconds`
    (e.g. a 60s window means every request between :00 and :59 of a minute
    shares one bucket) — simpler and cheap-to-clean-up than a true sliding
    window, and generous-enough limits make the fixed-window edge effect
    (up to ~2x limit right at a window boundary) a non-issue here.
    """
    now = datetime.now(timezone.utc)
    bucket_seconds = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(bucket_seconds, tz=timezone.utc)

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

    current_count = row["count"] if row else 1
    return current_count <= limit


def client_key(request, bucket: str) -> str:
    """Build a rate-limit key from the request's client IP and a bucket
    name (e.g. "login", "register") so different routes don't share limits.

    Falls back to request.client.host (works for local dev / direct
    connections); Vercel and most reverse proxies set X-Forwarded-For with
    the real client IP as the first entry, which takes priority when present
    since request.client.host would otherwise be the proxy's own address.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"{bucket}:{ip}"


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
