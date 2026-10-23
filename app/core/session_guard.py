"""Server-side checks on the signed session cookie.

The cookie alone proves "the server issued this", not "this is still allowed".
Two things need the server's word: a session version, bumped on logout and on a
password change so older cookies die at once, and the user row itself, which
may have been disabled or deleted. This middleware sits inside
SessionMiddleware and, when either check fails, empties the session so every
route downstream sees a logged-out request (the cookie is then cleared).

Cookies issued before session versions existed carry no `sv`; they count as
version 0, which is every user's starting version, so deploying this does not
sign anyone out. If the lookup itself fails the request is let through and the
failure is logged: during a database outage the app is mostly unusable anyway,
and locking every elderly user out would make it worse.
"""
import logging
import time

from app.db import queries as db

logger = logging.getLogger(__name__)

# A login without "remember me" is meant to end with the browser, but a copied
# cookie would outlive that, so it also carries a server-checked expiry.
SESSION_NO_REMEMBER_SECONDS = 12 * 60 * 60

_SKIP_PREFIXES = ("/static/", "/_next/", "/health")


async def _load_state(user_id):
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await c.execute("SELECT session_version, is_active FROM users WHERE id = ?", (user_id,))
        return c.fetchone()
    finally:
        await conn.close()


def _drop_login(session: dict) -> None:
    language = session.get("language")
    session.clear()
    if language:
        session["language"] = language


class SessionRevocationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            session = scope.get("session")
            if session and session.get("user_id") is not None and not scope["path"].startswith(_SKIP_PREFIXES):
                if not await self._still_valid(session):
                    _drop_login(session)
        await self.app(scope, receive, send)

    @staticmethod
    async def _still_valid(session) -> bool:
        expires = session.get("exp")
        if expires is not None and time.time() > expires:
            return False
        try:
            row = await _load_state(session["user_id"])
        except Exception as e:
            logger.warning("session check skipped (%s)", type(e).__name__)
            return True
        if row is None or row["is_active"] is False:
            return False
        return row["session_version"] == session.get("sv", 0)
