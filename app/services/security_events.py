"""Security audit trail: who tried to sign in, who got locked out, who changed
a password.

Each event goes to two places: one JSON line on the `app.security` logger (so it
shows up in the platform's runtime logs) and one row in `security_events` (so it
can be queried and kept longer than the log retention). Neither ever holds a
password, a verification code, a token or a plain email address: the address is
stored as a keyed hash, which still lets one account's events be found.

Recording is best effort. It must never turn a sign-in into an error, so any
failure is swallowed (and noted without detail).
"""
import asyncio
import hashlib
import hmac
import json
import logging

from app.core import config
from app.db import queries as db
from app.services.rate_limit import client_ip

logger = logging.getLogger("app.security")

_WRITE_TIMEOUT_SECONDS = 2.0
_USER_AGENT_MAX = 200


def email_hash(email: str) -> str:
    """Keyed, case-insensitive hash of an address (same input, same output)."""
    message = b"security-event-email:" + email.strip().lower().encode()
    return hmac.new(config.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


async def _insert(event, user_id, hashed_email, ip, user_agent, detail) -> None:
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await c.execute(
            "INSERT INTO security_events (event, user_id, email_hash, ip, ua, detail) "
            "VALUES (?, ?, ?, ?, ?, CAST(? AS jsonb))",
            (event, user_id, hashed_email, ip, user_agent, json.dumps(detail) if detail else None),
        )
        await conn.commit()
    finally:
        await conn.close()


async def record_event(event: str, *, request=None, user_id: int | None = None, email: str | None = None, detail: dict | None = None) -> None:
    try:
        ip = client_ip(request) if request is not None else None
        user_agent = request.headers.get("user-agent", "")[:_USER_AGENT_MAX] if request is not None else None
        hashed_email = email_hash(email) if email else None
        line = {"event": event, "user_id": user_id, "email_hash": hashed_email, "ip": ip, "detail": detail or {}}
        # json.dumps escapes newlines, so a hostile value cannot add a log line.
        logger.info("[SECURITY_EVENT] %s", json.dumps(line, ensure_ascii=True))
        await asyncio.wait_for(_insert(event, user_id, hashed_email, ip, user_agent, detail), _WRITE_TIMEOUT_SECONDS)
    except Exception as e:
        logger.warning("security event %s was not stored (%s)", event, type(e).__name__)
