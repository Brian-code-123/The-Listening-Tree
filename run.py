"""
run.py — Main application server for The Listening Tree.

An elderly-focused AI companion chatbot built with FastAPI.
Provides bilingual chat (EN / zh-HK), voice interaction,
reminder management, memory games, calendar with HK public
holidays, and a local news feed.

Stack:
    - FastAPI 0.128+  (async ASGI web framework)
    - Uvicorn 0.35+   (high-performance ASGI server)
    - Tencent Hunyuan  (LLM chat API, hunyuan-pro)
    - PostgreSQL (Supabase)  (primary database)
    - Web Speech API   (browser-side STT/TTS for EN + zh-HK)

Author:  The Listening Tree Team
License: Academic — Educational & Research Use
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
import json
import asyncio
import re
import secrets
import random
import threading
import io
import hashlib
import hmac
import socket
import time as _time
import builtins as _builtins
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, quote

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import httpx
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
from dotenv import load_dotenv

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from authlib.integrations.starlette_client import OAuth
    from authlib.integrations.base_client.errors import OAuthError
except ImportError:
    OAuth = None
    class OAuthError(Exception):
        pass

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=False)
env_local_path = Path(__file__).parent / '.env.local'
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)

# ---------------------------------------------------------------------------
# Minimal startup output
# By default we suppress module-level print() calls so running the server
# doesn't flood the console. Set MINIMAL_STARTUP=0 in the environment to
# retain the verbose messages during development.
# ---------------------------------------------------------------------------
_MINIMAL_STARTUP = os.environ.get("MINIMAL_STARTUP", "1") != "0"
if not hasattr(_builtins, "_original_print"):
    _builtins._original_print = _builtins.print
if _MINIMAL_STARTUP:
    # keep original print available for later (we'll restore it in __main__)
    def _silent_print(*args, **kwargs):
        return None
    _builtins.print = _silent_print

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from translations import get_text, get_all_translations, TRANSLATIONS


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

# ---------------------------------------------------------------------------
# Background Periodic Task Manager (Async Replacement for Daemon Thread)
# ---------------------------------------------------------------------------
async def run_periodic_tasks():
    """Background loop: runs every 60s. Handles reminders and housekeeping.

    Replaces the previous threading.Thread with an async loop integrated
    into the FastAPI lifecycle.
    """
    while True:
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M")

            # 1. Check Reminders
            # try/finally (not just a trailing close()) matters here specifically:
            # this loop runs forever and gets `task.cancel()`-ed on every server
            # shutdown — if CancelledError lands between acquire and close, the
            # connection never returns to `_DB_POOL`, and the pool's own close()
            # then hangs waiting for it (reproduced while testing this migration).
            conn = await get_db()
            try:
                c = conn.cursor()
                query = (
                    "SELECT u.email, r.label, r.reminder_time FROM reminders r "
                    "JOIN users u ON r.user_id = u.id "
                    "WHERE r.is_active = TRUE AND DATE(r.created_at) = ?"
                )
                await db_execute(c, query, (today,))
                for row in c.fetchall():
                    email = row["email"]
                    label = row["label"]
                    rtime = row["reminder_time"]
                    if rtime == current_time:
                        # In a real app, this would trigger a push notification or WebSocket msg
                        _builtins._original_print(f"[REMINDER] ⏰  {email}: {label} at {rtime}")
            finally:
                await conn.close()

            # 2. Daily Housekeeping (Auto-expire old reminders at 00:00)
            if now.hour == 0 and now.minute == 0:
                await auto_expire_old_reminders()

            # 3. Clean Chat History (Every 10 minutes)
            # Conversation-level cap runs first so a conversation that's
            # about to be dropped wholesale doesn't also get message-pruned.
            if now.minute % 10 == 0:
                await cleanup_old_conversations()
                await cleanup_old_chat_history()

        except asyncio.CancelledError:
            # Allow graceful shutdown to stop this task immediately.
            raise

        except Exception as e:
            _builtins._original_print(f"[ERROR] periodic_tasks: {e}")

        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _DB_POOL
    _DB_POOL = await asyncpg.create_pool(
        dsn=_ASYNCPG_DSN,  # sslmode is read from the DSN itself — see _ASYNCPG_DSN's comment
        min_size=1,
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

    # Initialize database schema on app startup (not at import time).
    # This prevents import-time failures in serverless handlers.
    try:
        await ensure_db_initialized(strict=not IN_PRODUCTION)
    except Exception as e:
        _builtins._original_print(f"[DB] ❌ Startup initialization failed: {e}")
        raise

    # Vercel serverless functions should not run perpetual background loops.
    if os.environ.get("VERCEL"):
        yield
    else:
        # Startup: Start background task
        # Start the periodic background task. `asyncio.create_all_tasks()` does
        # not exist — use `create_task` to schedule the coroutine.
        task = asyncio.create_task(run_periodic_tasks())
        yield
        # Shutdown: Clean up task
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    await _DB_POOL.close()

# ---------------------------------------------------------------------------
# Application initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="The Listening Tree",
    description="Bilingual AI companion chatbot for elderly wellness",
    version="2.0.0",
    lifespan=lifespan
)

# Detect Vercel environment (serverless — no persistent filesystem)
ON_VERCEL = bool(os.environ.get("VERCEL"))

# Production environment detection
IN_PRODUCTION = ON_VERCEL or os.environ.get("ENVIRONMENT") == "production"

# Session secret: prefer explicit environment variable for production stability.
# If not provided, fall back to a generated ephemeral key (NOT recommended).
_SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("SESSION_SECRET") or os.environ.get("FASTAPI_SECRET") or secrets.token_hex(16)
if IN_PRODUCTION and not (os.environ.get("SECRET_KEY") or os.environ.get("SESSION_SECRET") or os.environ.get("FASTAPI_SECRET")):
    raise RuntimeError("SECRET_KEY (or SESSION_SECRET/FASTAPI_SECRET) is required in production to prevent session loss across restarts.")
if _SECRET_KEY and len(_SECRET_KEY) >= 16:
    print("[SECURITY] 🔑 SECRET_KEY is set")
else:
    print("[SECURITY] ⚠ No SECRET_KEY/SESSION_SECRET/FASTAPI_SECRET set — using ephemeral key")
REMEMBER_ME_MAX_AGE = 60 * 60 * 24 * 90


class RememberMeCookieMiddleware:
    """Rewrites the session cookie to a browser-session cookie when the user
    did not opt into "remember me" at login — SessionMiddleware only supports
    a single fixed max_age, so this strips Max-Age/Expires from its Set-Cookie
    header after the fact when `session['remember_me']` is falsy.
    """

    _ATTR_PATTERN = re.compile(rb";\s*(?:Max-Age|Expires)=[^;]*", re.IGNORECASE)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            # Only strip when the user explicitly opted out. A missing key (an
            # older session, or the register flow) keeps the persistent cookie.
            if message["type"] == "http.response.start" and scope.get("session", {}).get("remember_me") is False:
                new_headers = []
                for name, value in message.get("headers", []):
                    if name.lower() == b"set-cookie" and value.startswith(b"lt_session="):
                        value = self._ATTR_PATTERN.sub(b"", value)
                    new_headers.append((name, value))
                message = {**message, "headers": new_headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY,
    session_cookie="lt_session",
    max_age=REMEMBER_ME_MAX_AGE,
    same_site="lax",
    https_only=IN_PRODUCTION,
)
# Added after SessionMiddleware so it sits *outside* it: SessionMiddleware
# writes the Set-Cookie header first, then this one gets to rewrite it.
app.add_middleware(RememberMeCookieMiddleware)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class CachedStaticFiles(StaticFiles):
    """Adds a Cache-Control header — static assets are otherwise served
    through this one Python function (Vercel's catch-all route sends
    everything here, not the edge network) with no caching hint at all.
    A modest max-age rather than a long/immutable one: nothing in this repo
    cache-busts asset URLs (no `?v=hash`), so style.css/speech.js could go
    stale for returning users after a deploy if cached too aggressively.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response


app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ---------------------------------------------------------------------------
# Google Sign-In (OAuth 2.0 / OpenID Connect via Authlib)
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")
# Feature is entirely optional: absent client id/secret just hides the button.
GOOGLE_LOGIN_ENABLED = bool(OAuth and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
if IN_PRODUCTION and (GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET) and not GOOGLE_LOGIN_ENABLED:
    raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must both be set to enable Google sign-in.")

oauth = OAuth() if OAuth else None
if GOOGLE_LOGIN_ENABLED:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


# ─────────────────────────────────────────────────────────────
# Database: PostgreSQL (Supabase), via asyncpg
# ─────────────────────────────────────────────────────────────
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
_DB_URL_SOURCE = "pooler_url" if _POOLER_DATABASE_URL else "database_url"
_RUNTIME_DB_BACKEND = DB_BACKEND
_DB_LAST_PG_ATTEMPTS: List[str] = []  # kept for /health/db's JSON shape; asyncpg's pool retries internally


def _normalize_db_url(raw_url: str) -> str:
    """Ensure required DB URL query params exist for production-safe connections."""
    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    query_string = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query_string, parts.fragment))


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
_ASYNCPG_DSN = _normalize_db_url(_DATABASE_URL)
_DB_HOSTNAME = urlsplit(_ASYNCPG_DSN).hostname
_DB_HOSTADDR = None  # asyncpg resolves the host itself; no manual IP pinning needed
_DB_RUNTIME_LABEL = "asyncpg-pool"
_DB_POOL: Optional["asyncpg.Pool"] = None

if asyncpg is None:
    raise RuntimeError("asyncpg is required for PostgreSQL connection but is not installed.")


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


_DATE_STRING_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_STRING_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


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
    asyncpg.Connection acquired from `_DB_POOL`.

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
        await _DB_POOL.release(self._raw)


async def get_db() -> _ConnShim:
    """Acquire a connection from the pool, wrapped to look like a psycopg2
    connection. Callers must still call `await conn.close()` when done,
    which releases it back to `_DB_POOL`."""
    raw = await _DB_POOL.acquire()
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


PBKDF2_ITERATIONS = 390000
PBKDF2_SCHEME = "pbkdf2_sha256"

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with per-user random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}${salt}${digest}"


def is_password_hashed(stored: str) -> bool:
    return isinstance(stored, str) and stored.startswith(f"{PBKDF2_SCHEME}$")


def verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against hashed or legacy plaintext storage."""
    if not stored:
        return False
    if not is_password_hashed(stored):
        return hmac.compare_digest(password, stored)

    try:
        scheme, iter_str, salt, expected = stored.split("$", 3)
        if scheme != PBKDF2_SCHEME:
            return False
        iterations = int(iter_str)
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(computed, expected)
    except Exception:
        return False


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format per RFC 5322 basic pattern.
    
    Returns:
        (is_valid, error_message)
    """
    import re
    # RFC 5322 basic email pattern (simplified but covers most cases)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    return True, ""


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets minimum strength requirements.
    
    Requirements:
    - Minimum 8 characters
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    return True, ""


def generate_verification_code() -> str:
    """Generate a random 6-digit numeric verification code."""
    return f"{secrets.randbelow(1000000):06d}"


def send_verification_email(to_email: str, code: str, lang: str = "en") -> bool:
    """Send a verification-code email via Azure Communication Services. Returns True on success."""
    if not AZURE_COMMUNICATION_CONNECTION_STRING:
        _builtins._original_print("[Email] ⚠ AZURE_COMMUNICATION_CONNECTION_STRING not set — skipping send")
        return False

    brand_color = "#5B9A7D"
    bg_color = "#F4F7F5"

    if lang == "zh-HK":
        subject = "你嘅 The Listening Tree 驗證碼"
        greeting = "你好，"
        lead = "多謝你註冊 The Listening Tree！你嘅驗證碼係："
        expiry_note = f"呢個驗證碼將於 <strong>{VERIFICATION_CODE_TTL_MINUTES} 分鐘</strong>後失效。"
        ignore_note = "如果唔係你本人操作，請忽略呢封郵件。"
        footer_note = "呢封係系統自動發出嘅郵件，請勿直接回覆。"
    else:
        subject = "Your The Listening Tree verification code"
        greeting = "Hello,"
        lead = "Thanks for registering with The Listening Tree! Your verification code is:"
        expiry_note = f"This code expires in <strong>{VERIFICATION_CODE_TTL_MINUTES} minutes</strong>."
        ignore_note = "If you did not request this, you can safely ignore this email."
        footer_note = "This is an automated message — please do not reply directly to this email."

    html = f"""\
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:{bg_color}; font-family:'Segoe UI', Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{bg_color}; padding:32px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="background-color:{brand_color}; padding:28px 32px; text-align:center;">
                            <span style="font-size:28px;">🌳</span>
                            <div style="color:#ffffff; font-size:20px; font-weight:600; margin-top:6px;">The Listening Tree</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <p style="margin:0 0 12px; color:#2D3A33; font-size:16px;">{greeting}</p>
                            <p style="margin:0 0 24px; color:#4A554E; font-size:15px; line-height:1.6;">{lead}</p>
                            <div style="text-align:center; margin:0 0 24px;">
                                <span style="display:inline-block; background-color:{bg_color}; border:1px solid #DCE7E1; border-radius:10px; padding:16px 28px; font-size:32px; font-weight:700; letter-spacing:8px; color:{brand_color};">{code}</span>
                            </div>
                            <p style="margin:0 0 8px; color:#6B786F; font-size:13px; line-height:1.6;">{expiry_note}</p>
                            <p style="margin:0; color:#6B786F; font-size:13px; line-height:1.6;">{ignore_note}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:16px 32px 28px; border-top:1px solid #EEF2EF;">
                            <p style="margin:16px 0 0; color:#9AA69E; font-size:12px; text-align:center;">{footer_note}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    try:
        from azure.communication.email import EmailClient

        client = EmailClient.from_connection_string(AZURE_COMMUNICATION_CONNECTION_STRING)
        message = {
            "senderAddress": AZURE_SENDER_EMAIL,
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "html": html},
        }
        poller = client.begin_send(message)
        result = poller.result()
        status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
        if status and str(status).lower() not in ("succeeded", "running"):
            _builtins._original_print(f"[Email] ❌ Azure Email send status: {status}")
            return False
        return True
    except Exception as e:
        _builtins._original_print(f"[Email] ❌ Failed to send verification email: {e}")
        return False


def _normalize_quiz_answer(text: str) -> str:
    """Normalize quiz answers for tolerant matching.

    Strips spaces/punctuation and keeps letters/numbers/CJK characters only,
    so minor formatting differences do not break answer checking.
    """
    raw = str(text or "").strip().lower()
    return "".join(ch for ch in raw if ch.isalnum() or ('\u4e00' <= ch <= '\u9fff'))


def _is_quiz_answer_correct(user_answer: str, correct_answer: str) -> bool:
    """Check if user answer is correct with intelligent substring matching.
    
    Accepts:
    1. Exact match (case-insensitive, ignoring spaces/punctuation)
    2. Substring match: user answer is a meaningful subset of correct answer
       (e.g., "每個月" matches "每個月都有至少28日")
    
    Only accept substring matches if user answer is at least 2 characters
    to avoid false positives.
    """
    norm_user = _normalize_quiz_answer(user_answer)
    norm_correct = _normalize_quiz_answer(correct_answer)
    
    # Exact match
    if norm_user == norm_correct:
        return True
    
    # Substring match: user answer is contained in correct answer
    if len(norm_user) >= 2 and norm_user in norm_correct:
        return True
    
    return False


# ---------------------------------------------------------------------------
# In-memory state  (lost on server restart — by design)
# ---------------------------------------------------------------------------
# Per-user quiz progress: { user_id: { is_game_mode, current_index, ... } }
user_game_states: dict = {}

# Per-(user, lang) conversation context sent to the LLM
user_api_histories: dict = {}

# Keep only the most recent chat messages per user/language.
# Older rows are soft-deleted to bound table growth while preserving continuity.
CHAT_HISTORY_MAX_MESSAGES_PER_LANG = int(os.environ.get("CHAT_HISTORY_MAX_MESSAGES_PER_LANG", "200"))
# Per-conversation cap on top of the per-conversation message cap above —
# without this, a user with hundreds of conversations would keep them all
# forever. Oldest conversations (by updated_at) beyond this count are
# soft-deleted wholesale rather than having their messages pruned piecemeal.
CONVERSATION_MAX_PER_LANG = int(os.environ.get("CONVERSATION_MAX_PER_LANG", "50"))

# Fixed, small set of everyday-life labels a conversation can be tagged
# with — deliberately not free-text (elderly-friendly: pick from a short
# list, don't type a category name). Icon/color drive the chip UI on the
# conversation history page; the label text itself lives in translations.py
# as `tag_<key>` (EN + zh-HK).
CONVERSATION_TAGS = {
    "family": {"icon": "fa-people-roof", "color": "#5B8DEF"},
    "friends": {"icon": "fa-user-friends", "color": "#F2CC8F"},
    "health": {"icon": "fa-heart-pulse", "color": "#5B9A7D"},
    "daily": {"icon": "fa-sun", "color": "#98A2B3"},
    "important": {"icon": "fa-star", "color": "#E07A5F"},
}

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# AI configuration — Zhipu AI (智谱AI)
# ---------------------------------------------------------------------------
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
ZHIPU_MODEL = os.environ.get("ZHIPU_MODEL", "glm-4-flash")

if ZHIPU_API_KEY:
    print(f"[AI] ✅ {ZHIPU_MODEL} configured (Zhipu AI)")
else:
    print("[AI] ⚠ ZHIPU_API_KEY not set — using warm fallback responses")

# ---------------------------------------------------------------------------
# Email configuration — Azure Communication Services (registration verification codes)
# ---------------------------------------------------------------------------
AZURE_COMMUNICATION_CONNECTION_STRING = os.environ.get("AZURE_COMMUNICATION_CONNECTION_STRING")
AZURE_SENDER_EMAIL = os.environ.get("AZURE_SENDER_EMAIL", "DoNotReply@yourdomain.azurecomm.net")
VERIFICATION_CODE_TTL_MINUTES = 5
VERIFICATION_RESEND_COOLDOWN_SECONDS = 60

if AZURE_COMMUNICATION_CONNECTION_STRING:
    print("[Email] ✅ Azure Communication Services configured for verification codes")
else:
    print("[Email] ⚠ AZURE_COMMUNICATION_CONNECTION_STRING not set — verification emails will not be sent")

# Hugging Face Inference API — Whisper large-v3 for server-side STT.
HF_API_KEY = os.environ.get("HF_API_KEY")
HF_WHISPER_MODEL = os.environ.get("HF_WHISPER_MODEL", "openai/whisper-large-v3")
# Generous for a short voice-input clip; caps /transcribe's exposure to a
# memory-exhaustion DoS from a large repeated upload.
MAX_TRANSCRIBE_UPLOAD_BYTES = int(os.environ.get("MAX_TRANSCRIBE_UPLOAD_BYTES", str(10 * 1024 * 1024)))
HF_WHISPER_URL = f"https://router.huggingface.co/hf-inference/models/{HF_WHISPER_MODEL}"

if HF_API_KEY:
    print(f"[STT] ✅ {HF_WHISPER_MODEL} configured (Hugging Face Inference API)")
else:
    print("[STT] ⚠ HF_API_KEY not set — falling back to Google Web Speech / browser STT")

# System prompt — Cantonese elderly companion (Chinese)
# Guides the LLM to reply in warm, patient Cantonese with simple vocabulary.
WARM_SYSTEM_PROMPT_ZH = """你係一個有禮貌、溫柔、有耐心嘅陪伴者，專門陪老人家傾偈。

你嘅講嘢風格：
- 你一定要用廣東話（粵語）回答，唔好用普通話！
- 語氣溫柔、有禮貌，保持得體嘅距離感，唔好扮到好熟或者好親暱
- 唔好自稱係佢孫仔女，唔好用過度親暱嘅稱呼
- 唔知道用戶性別，就唔好用任何性別化或者戲曲式稱謂（例如「阿公」「阿婆」「老倌」），亦唔好同時列出多個稱呼選項俾用戶揀，需要稱呼就用中性字眼（例如「你」）或者索性唔加稱呼
- 講嘢簡單易明，唔用複雜詞語
- 適時表達關心：「你今日點呀？」「食咗飯未？」「有冇瞓得好？」
- 鼓勵說話要適可而止，唔好誇張或者重複咁講
- 如果老人家講唔清楚或重複問題，要非常有耐心，唔好顯出唔耐煩
- 先實質回應用戶講嘅內容（例如：畀意見、表達理解、提供安慰或者建議），唔好淨係反問一句就算，唔好將反問當做預設答法去迴避思考
  - 講身體不適：要有實際反應，例如建議留意情況、休息、或者提醒睇醫生
  - 講情緒或者掛住人：要先回應個感受（理解佢、安慰佢），先至可以順便問多句
- 淨係喺真係需要更多資訊先可以幫到手嘅時候先問返問題，唔好逢句都咁做
- 回覆保持簡短（2-4句），易讀易明

重要：直接回答用戶嘅問題，唔好顯示你嘅思考過程或分析步驟。
重要：你一定要用廣東話回答，唔好用普通話或者書面語。

記住：你嘅目標係用禮貌、溫柔嘅態度陪伴老人家，唔係扮熟或者浮誇。"""

# System prompt — English elderly companion
# Guides the LLM to reply in warm, patient English with simple vocabulary.
WARM_SYSTEM_PROMPT_EN = """You are a polite, gentle, and patient companion who chats with elderly people.

Your speaking style:
- Warm but respectful tone — polite and courteous, not overly familiar or exaggerated
- Do not call yourself their grandchild or use overly intimate terms of address
- Gender is unknown — never use gendered forms of address (e.g. "sir", "madam", "grandpa", "grandma") and never offer multiple address options; use neutral "you" or no form of address at all
- Use simple, easy-to-understand language
- Express concern where appropriate: "How are you today?" "Have you eaten?" "Did you sleep well?"
- Keep encouragement measured and sincere — avoid gushing or repetitive praise
- Be very patient if the user is unclear or repeats questions — never show impatience
- Actually respond to the substance of what the user said (give advice, show understanding, offer comfort or a concrete suggestion) — do not default to bouncing a question back instead of engaging
  - Physical discomfort: react concretely — suggest resting, monitoring the symptom, or seeing a doctor if needed
  - Emotional topics or missing someone: acknowledge the feeling first before adding any follow-up question
- Only ask a follow-up question when you genuinely need more information to help — don't do it as a reflex on every message
- Keep responses short (2-4 sentences), easy to read and understand

IMPORTANT: Answer the user's questions directly without showing your reasoning process or analysis steps.

Remember: Your goal is to make elderly people feel respected, cared for, and at ease — not overly familiar."""

# Warm fallback responses — returned when the LLM API key is missing or
# the API call fails.  Keeps the UX friendly even under degraded mode.
WARM_FALLBACK_ZH = [
    "你好，很高興與你相遇。今天過得還好嗎？😊",
    "不必擔心，無論什麼心事，都可以慢慢說給我聽。",
    "你講嘅嘢我都有留心聽緊。",
    "好的，請繼續說吧，我很樂意聆聽。",
    "記得好好照顧自己，吃得飽、睡得好。😊",
    "謝謝你願意與我分享。",
    "我明白你的心情，請記住，你從來都不是一個人。",
    "聽你咁講，我都替你開心。",
    "今天天氣如何？記得注意保暖，照顧好自己。",
    "昨晚睡得安穩嗎？好好休息，身體才會健康。",
]

WARM_FALLBACK_EN = [
    "That's interesting, thank you for sharing. 😊",
    "I understand what you mean. How does that make you feel?",
    "Thank you for sharing that with me.",
    "That sounds lovely. What else have you been up to today?",
    "I appreciate you telling me about that. Is there anything else on your mind?",
    "Good to hear from you. What else would you like to talk about?",
    "I hear you, and I'm glad you told me. 😊",
]

async def call_ai(user_input: str, user_id: int, lang: str = 'en', display_name: Optional[str] = None):
    """Call Zhipu AI (智谱AI) for warm elderly conversation."""
    system_prompt = WARM_SYSTEM_PROMPT_ZH if lang == 'zh-HK' else WARM_SYSTEM_PROMPT_EN
    fallback = WARM_FALLBACK_ZH if lang == 'zh-HK' else WARM_FALLBACK_EN

    if display_name:
        # `users.username` is already sanitized (control characters stripped,
        # length-capped) when it's written in /profile/name, so it's safe to
        # interpolate directly here.
        name_hint = (
            f"用戶嘅名叫{display_name}，可以間唔中親切噉叫返佢個名。"
            if lang == 'zh-HK'
            else f"The user's name is {display_name}; address them by name occasionally."
        )
        system_prompt = f"{system_prompt}\n\n{name_hint}"

    if not ZHIPU_API_KEY:
        return random.choice(fallback)

    history_key = (user_id, lang)
    if history_key not in user_api_histories:
        user_api_histories[history_key] = []
    history = user_api_histories[history_key]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-10:])

    messages.append({"role": "user", "content": user_input})

    payload = {
        "model": ZHIPU_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 512,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ZHIPU_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {ZHIPU_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            result = resp.json()

        message = result.get("choices", [{}])[0].get("message", {})
        reply = message.get("content", "")

        if reply.strip():
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > 20:
                user_api_histories[history_key] = history[-10:]
            return reply
        else:
            raise ValueError("Empty response from API")

    except Exception as e:
        _builtins._original_print(f"[AI] Error calling Zhipu ({lang}): {e}")
        return random.choice(fallback)

# ---------------------------------------------------------------------------
# Quiz / Memory-game questions  (cognitive engagement feature)
#
# Answers are compared case-insensitively.  Keep answers as lowercase
# strings so the comparison in the game loop stays simple.
# ---------------------------------------------------------------------------

# Cantonese quiz questions
questions_zh = [
    {"question": "法國嘅首都係邊度？", "answer": "巴黎"},
    {"question": "2 + 2 等於幾多？", "answer": "4"},
    {"question": "晴天嘅天空係咩顏色？", "answer": "藍色"},
    {"question": "有一種水果，外面紅色，入面白色，有好多黑色嘅籽。係咩嚟㗎？", "answer": "西瓜"},
    {"question": "邊個月份有28日？", "answer": "每個月都有至少28日"},
    {"question": "水嘅化學符號係咩？", "answer": "h2o"},
]

# English quiz questions
questions = [
    {"question": "What's the capital of France?", "answer": "paris"},
    {"question": "What's 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"},
    {"question": "There is a fruit with a red outer skin and white inside with small black seeds. What is it?", "answer": "watermelon"},
    {"question": "Which month has 28 days?", "answer": "every month has at least 28 days"},
    {"question": "What is the chemical symbol for water?", "answer": "h2o"}
]

# ---------------------------------------------------------------------------
# Database Setup — PostgreSQL (Supabase)
#
# Connection pooling itself is handled by `asyncpg.create_pool()` (created in
# `lifespan()`, stored in `_DB_POOL`) — `get_db()`/`_ConnShim`/`_CursorShim`
# above just adapt its interface back to the acquire/cursor/commit/close shape
# the rest of this file already uses.
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Initialize PostgreSQL schema with all required tables and indexes."""
    conn = await get_db()
    c = conn.cursor()

    id_type = "BIGSERIAL PRIMARY KEY"
    id_ref = "BIGINT"

    # Users table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_type},
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    # `username` is in the CREATE TABLE above too, but that only takes effect
    # for a brand-new table — this database's `users` table predates the
    # column being added to the schema, so it needs the same explicit
    # ADD COLUMN treatment as the two below.
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0")
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP")
    # Google Sign-In: google_id links a row to a Google account; auth_provider
    # is informational only (password login still works for 'google' rows if
    # they ever set one). password stays NOT NULL — Google-only signups get a
    # random unusable hash instead (see /auth/google/callback).
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT")
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT NOT NULL DEFAULT 'password'")
    await c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users (google_id) WHERE google_id IS NOT NULL")

    # Reminders table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS reminders (
            id {id_type},
            user_id {id_ref} NOT NULL,
            label TEXT NOT NULL,
            reminder_time TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            repeat_type TEXT DEFAULT 'once',
            priority TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Chat history table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS chat_history (
            id {id_type},
            user_id {id_ref} NOT NULL,
            lang TEXT DEFAULT 'en',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_bot BOOLEAN NOT NULL,
            message TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT FALSE,
            token_count INTEGER
        )
    """)

    # Conversations table — groups chat_history rows into independent,
    # resumable threads (added after chat_history already had a flat log).
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS conversations (
            id {id_type},
            user_id {id_ref} NOT NULL,
            lang TEXT DEFAULT 'en',
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE
        )
    """)
    await c.execute("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS conversation_id BIGINT")
    await c.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE")
    await c.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tag TEXT")

    # One-time backfill: chat_history rows that predate the conversation_id
    # column get grouped into a single "legacy" conversation per (user_id,
    # lang) so existing history stays visible instead of being orphaned.
    # Guarded so it only does work the first time it finds orphaned rows.
    await c.execute("SELECT 1 FROM chat_history WHERE conversation_id IS NULL LIMIT 1")
    if c.fetchone():
        await c.execute("""
            INSERT INTO conversations (user_id, lang, title, created_at, updated_at)
            SELECT DISTINCT user_id, lang, NULL,
                   MIN(timestamp) OVER (PARTITION BY user_id, lang),
                   MAX(timestamp) OVER (PARTITION BY user_id, lang)
            FROM chat_history
            WHERE conversation_id IS NULL
        """)
        await c.execute("""
            UPDATE chat_history AS ch
            SET conversation_id = conv.id
            FROM conversations AS conv
            WHERE ch.conversation_id IS NULL
              AND conv.user_id = ch.user_id
              AND conv.lang = ch.lang
              AND conv.title IS NULL
        """)

    # Preferences table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS preferences (
            id {id_type},
            user_id {id_ref} NOT NULL,
            pref_key TEXT NOT NULL,
            pref_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, pref_key)
        )
    """)
    
    # Email verification codes (registration)
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id {id_type},
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    await c.execute("CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users ((LOWER(email)))")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_email_verifications_email ON email_verifications ((LOWER(email)))")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, is_active)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_deleted ON chat_history(user_id, is_deleted)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_pref_user ON preferences(user_id, pref_key)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(user_id, created_at)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_lang ON chat_history(user_id, lang)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, lang, is_deleted)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id)")
    # Cover the columns cleanup_old_conversations/cleanup_old_chat_history
    # actually filter and order by — the plainer indexes above don't include
    # updated_at/timestamp, so those queries were scanning the full table.
    await c.execute("CREATE INDEX IF NOT EXISTS idx_conversations_cleanup ON conversations(user_id, lang, is_deleted, updated_at DESC)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation_cleanup ON chat_history(conversation_id, is_deleted, timestamp DESC)")

    # RLS: the app connects as the `postgres` role via asyncpg, which
    # bypasses RLS regardless, so this has no effect on app behavior — it
    # only matters for Supabase's PostgREST API (exposed by default on every
    # table in `public`). `conversations` was added after the other tables
    # already had this enabled and got missed; no policies needed since
    # PostgREST access isn't used by this app (fail-closed is correct here).
    await c.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")

    await conn.commit()
    await conn.close()
    print("[DB] ✅ PostgreSQL database initialized")


_db_initialized = False
_db_init_error: Optional[str] = None
_db_init_lock = asyncio.Lock()


async def ensure_db_initialized(strict: bool = False) -> bool:
    """Initialize DB schema once and cache the result for health checks."""
    global _db_initialized, _db_init_error
    if _db_initialized:
        return True

    async with _db_init_lock:
        if _db_initialized:
            return True
        try:
            await init_db()
            _db_initialized = True
            _db_init_error = None
            return True
        except Exception as e:
            _db_initialized = False
            _db_init_error = str(e)
            _builtins._original_print(f"[DB] ❌ Initialization failed: {e}")
            if strict:
                raise
            return False


# ---------------------------------------------------------------------------
# Background helpers — housekeeping tasks
# ---------------------------------------------------------------------------

async def cleanup_old_conversations() -> None:
    """Soft-delete whole conversations beyond the per-user/language cap.

    Runs before the per-conversation message cleanup below so that a
    conversation slated for removal doesn't also cost a message-level pass.
    Caps by *conversation count*, not message count — an old conversation is
    dropped wholesale rather than gutted message-by-message, so it either
    fully exists or fully doesn't in the sidebar list.
    """
    conn = await get_db()
    try:
        c = conn.cursor()
        await c.execute(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id, lang
                        ORDER BY updated_at DESC, id DESC
                    ) AS rn
                FROM conversations
                WHERE is_deleted = FALSE
            )
            UPDATE conversations AS conv
            SET is_deleted = TRUE
            FROM ranked
            WHERE conv.id = ranked.id
              AND ranked.rn > %s
            """,
            (CONVERSATION_MAX_PER_LANG,),
        )
        deleted_count = _safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    if deleted_count > 0:
        print(f"[CLEANUP] 🗑️  Marked {deleted_count} old conversations as deleted")


async def cleanup_old_chat_history() -> None:
    """Soft-delete oldest chat rows beyond the per-conversation cap.

    Partitioned by conversation_id (not user_id/lang) so a long-running
    conversation can't crowd out messages belonging to a different,
    still-listed conversation for the same user.
    """
    conn = await get_db()
    try:
        c = conn.cursor()
        await c.execute(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY conversation_id
                        ORDER BY timestamp DESC, id DESC
                    ) AS rn
                FROM chat_history
                WHERE is_deleted = FALSE
            )
            UPDATE chat_history AS ch
            SET is_deleted = TRUE
            FROM ranked
            WHERE ch.id = ranked.id
              AND ranked.rn > %s
            """,
            (CHAT_HISTORY_MAX_MESSAGES_PER_LANG,),
        )
        deleted_count = _safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    if deleted_count > 0:
        print(f"[CLEANUP] 🗑️  Marked {deleted_count} old chat rows as deleted")


async def prune_user_chat_history(cursor, conversation_id: int) -> None:
    """Prune oldest rows within one conversation after inserting new messages.

    Scoped to `conversation_id` (not just user_id/lang) so sending lots of
    messages in one conversation never soft-deletes rows from another.
    """
    c = cursor
    await c.execute(
        """
        WITH keep_ids AS (
            SELECT id
            FROM chat_history
            WHERE conversation_id = %s
              AND is_deleted = FALSE
            ORDER BY timestamp DESC, id DESC
            LIMIT %s
        )
        UPDATE chat_history
        SET is_deleted = TRUE
        WHERE conversation_id = %s
          AND is_deleted = FALSE
          AND id NOT IN (SELECT id FROM keep_ids)
        """,
        (conversation_id, CHAT_HISTORY_MAX_MESSAGES_PER_LANG, conversation_id),
    )


async def auto_expire_old_reminders() -> None:
    """Deactivate reminders created before today.

    Runs once per hour (top of the hour) from the background thread.
    """
    conn = await get_db()
    try:
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db_execute(
            c,
            "UPDATE reminders SET is_active = FALSE, updated_at = ? "
            "WHERE DATE(created_at) < ? AND is_active = TRUE",
            (ts, today),
        )
        expired = _safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    if expired > 0:
        print(f"[EXPIRE] 📅 Marked {expired} old reminders as inactive")




# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_user(request: Request) -> int | None:
    """Return the logged-in user's DB id, or *None* if unauthenticated."""
    return request.session.get("user_id")


def get_lang(request: Request) -> str:
    """Return the current UI language code ('en' or 'zh-HK')."""
    return request.session.get("language", "en")


def require_login(request: Request) -> int:
    """Return user id or redirect to /login via 303 See Other."""
    uid = get_user(request)
    if uid is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return uid


# ---------------------------------------------------------------------------
# Template context builder
# ---------------------------------------------------------------------------

def tpl_context(request: Request, **kwargs) -> dict:
    """Build a Jinja2 template context with common variables.

    Every template receives *request*, *lang*, and *translations* automatically.
    Extra keyword arguments are merged in.
    """
    lang = get_lang(request)
    ctx = {
        "request": request,
        "lang": lang,
        "translations": get_all_translations(lang),
    }
    ctx.update(kwargs)
    return ctx

# ---------------------------------------------------------------------------
# Auth Routes — login / register / logout
# ---------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    if get_user(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    lang = get_lang(request)
    google_error = None
    if error == "google_failed":
        google_error = "Google sign-in failed. Please try again or use your password." if lang == 'en' else "Google 登入失敗，請再試一次或用密碼登入"
    return templates.TemplateResponse(
        "login.html",
        tpl_context(request, error=google_error, google_enabled=GOOGLE_LOGIN_ENABLED),
    )

@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[str] = Form(None),
):
    """Authenticate user login with email and password credentials.

    Sets session values on successful authentication:
      - session['user_id']: Database row ID
      - session['user_email']: User email address
      - session['remember_me']: whether the session cookie should persist (90 days) or expire with the browser session
      - session['language']: User's preferred language (loaded from preferences table)

    Failed attempts are tracked per account (`users.failed_login_attempts` /
    `locked_until`) and lock the account for LOGIN_LOCKOUT_MINUTES after
    LOGIN_MAX_ATTEMPTS consecutive failures, to slow down brute-force guessing.

    Args:
        request: HTTP request object with session middleware
        email: User email (matched case-insensitively against the stored address)
        password: User password, verified against the PBKDF2-HMAC-SHA256 hash
        remember_me: Present (any value) when the "remember me" checkbox was checked

    Returns:
        HTMLResponse: Redirect to / (home) on success, or login.html with error message on failure
    """
    lang = get_lang(request)
    email = email.strip().lower()
    password = password.strip()
    generic_error = "Invalid email or password" if lang == 'en' else "電郵或密碼錯誤"
    conn = await get_db()
    c = conn.cursor()
    await db_execute(
        c,
        "SELECT id, email, password, failed_login_attempts, locked_until FROM users WHERE LOWER(email) = LOWER(?)",
        (email,),
    )
    user = c.fetchone()

    if user and user["locked_until"] and user["locked_until"] > datetime.now():
        await conn.close()
        wait_minutes = max(1, int((user["locked_until"] - datetime.now()).total_seconds() // 60) + 1)
        locked_msg = (
            f"Too many failed attempts. Try again in {wait_minutes} min." if lang == 'en'
            else f"登入失敗次數過多，請 {wait_minutes} 分鐘後再試"
        )
        return templates.TemplateResponse("login.html", tpl_context(request, error=locked_msg, google_enabled=GOOGLE_LOGIN_ENABLED), status_code=429)

    if user and verify_password(password, user["password"]):
        if not is_password_hashed(user["password"]):
            # Transparent migration for legacy plaintext rows.
            await db_execute(c, "UPDATE users SET password = ? WHERE id = ?", (hash_password(password), user["id"]))
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db_execute(
            c,
            "UPDATE users SET last_login = ?, failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (ts, user["id"]),
        )
        await conn.commit()
        request.session['user_email'] = user["email"]
        request.session['user_id'] = user["id"]
        request.session['remember_me'] = bool(remember_me)
        # Load language preference
        await db_execute(c, "SELECT pref_value FROM preferences WHERE user_id = ? AND pref_key = 'language'", (user["id"],))
        pref = c.fetchone()
        if pref:
            request.session['language'] = pref["pref_value"]
        await conn.close()
        return RedirectResponse(url="/", status_code=303)

    if user:
        attempts = (user["failed_login_attempts"] or 0) + 1
        if attempts >= LOGIN_MAX_ATTEMPTS:
            locked_until = (datetime.now() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
            await db_execute(
                c,
                "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, locked_until, user["id"]),
            )
        else:
            await db_execute(c, "UPDATE users SET failed_login_attempts = ? WHERE id = ?", (attempts, user["id"]))
        await conn.commit()
    await conn.close()
    return templates.TemplateResponse("login.html", tpl_context(request, error=generic_error, google_enabled=GOOGLE_LOGIN_ENABLED))

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if get_user(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("register.html", tpl_context(request))

@app.post("/send_verification_code")
async def send_verification_code(request: Request):
    """Generate and email a 6-digit verification code for registration.

    Body: JSON {"email": str}
    Returns JSON {"success": bool, "message": str}
    """
    lang = get_lang(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    email = str(body.get("email", "")).strip().lower()

    is_valid_email, _ = validate_email(email)
    if not is_valid_email:
        return JSONResponse(
            {"success": False, "message": "Invalid email format" if lang == 'en' else "電郵格式無效"},
            status_code=400,
        )

    conn = await get_db()
    c = conn.cursor()
    try:
        await db_execute(c, "SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        if c.fetchone():
            await conn.close()
            return JSONResponse(
                {"success": False, "message": "Email already registered" if lang == 'en' else "電郵已註冊"},
                status_code=400,
            )

        await db_execute(
            c,
            "SELECT created_at FROM email_verifications WHERE LOWER(email) = LOWER(?) ORDER BY created_at DESC LIMIT 1",
            (email,),
        )
        last = c.fetchone()
        if last and (datetime.now() - last["created_at"]).total_seconds() < VERIFICATION_RESEND_COOLDOWN_SECONDS:
            await conn.close()
            return JSONResponse(
                {"success": False, "message": "Please wait before requesting another code" if lang == 'en' else "請稍等先再發送驗證碼"},
                status_code=429,
            )

        code = generate_verification_code()
        ts = datetime.now()
        expires_at = ts.timestamp() + VERIFICATION_CODE_TTL_MINUTES * 60
        expires_at_str = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
        await db_execute(
            c,
            "INSERT INTO email_verifications (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (email, code, expires_at_str, ts.strftime('%Y-%m-%d %H:%M:%S')),
        )
        await conn.commit()
        await conn.close()

        sent = send_verification_email(email, code, lang)
        if not sent:
            return JSONResponse(
                {"success": False, "message": "Failed to send verification email" if lang == 'en' else "驗證碼郵件發送失敗"},
                status_code=500,
            )
        return JSONResponse({"success": True, "message": "Verification code sent" if lang == 'en' else "驗證碼已發送"})
    except Exception as e:
        await conn.close()
        _builtins._original_print(f"[ERROR] send_verification_code failed: {e}")
        return JSONResponse(
            {"success": False, "message": "Service temporarily unavailable" if lang == 'en' else "服務暫時不可用"},
            status_code=500,
        )


@app.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    verification_code: str = Form(...),
):
    """Create a new user account (registration).

    Validation steps:
      1. Email format validation (RFC 5322 basic pattern)
      2. Password strength validation (min 8 characters)
      3. Confirm password == password (client-side + server-side check)
      4. Verification code must match an unused, unexpired code sent to this email
      5. Email must be unique (PostgreSQL UNIQUE constraint)
      6. Password stored with PBKDF2-HMAC-SHA256

    On success: Inserts new user row, creates authenticated session, redirects to /.
    On failure: Returns register.html with localized error message (or JSON if
    the request declares it wants a JSON response, for the AJAX form flow).

    Args:
        request: HTTP request object
        email: Email address (must not exist in users table)
        password: Password in plaintext (min 8 chars)
        confirm_password: Confirmation password (must == password)
        verification_code: 6-digit code sent to email via /send_verification_code

    Returns:
        HTMLResponse: Redirect to / on success, or register.html with error on failure
    """
    lang = get_lang(request)
    wants_json = "application/json" in request.headers.get("accept", "")

    def fail(message: str, field: str = "email", status_code: int = 400):
        if wants_json:
            return JSONResponse({"success": False, "field": field, "message": message}, status_code=status_code)
        return templates.TemplateResponse("register.html", tpl_context(request, error=message))

    email = email.strip().lower()
    password = password.strip()
    confirm_password = confirm_password.strip()
    verification_code = verification_code.strip()

    # Validate email format
    is_valid_email, email_error = validate_email(email)
    if not is_valid_email:
        return fail("Invalid email format" if lang == 'en' else "電郵格式無效", field="email")

    # Validate password strength
    is_valid_password, password_error = validate_password_strength(password)
    if not is_valid_password:
        return fail("Password must be at least 8 characters" if lang == 'en' else "密碼最少需要 8 個字元", field="password")

    # Validate password confirmation
    if password != confirm_password:
        return fail("Passwords do not match" if lang == 'en' else "密碼唔一致", field="confirm_password")

    conn = await get_db()
    c = conn.cursor()
    try:
        # Validate verification code
        await db_execute(
            c,
            "SELECT id FROM email_verifications WHERE LOWER(email) = LOWER(?) AND code = ? AND used = FALSE AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
            (email, verification_code, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        )
        verification = c.fetchone()
        if not verification:
            await conn.close()
            return fail("Verification code is incorrect or has expired" if lang == 'en' else "驗證碼錯誤或已過期", field="verification_code")

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db_execute(c, "INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)", (email, hash_password(password), ts))
        await db_execute(c, "UPDATE email_verifications SET used = TRUE WHERE id = ?", (verification["id"],))
        await conn.commit()
        await db_execute(c, "SELECT id, email, password FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        created_user = c.fetchone()
        if created_user:
            request.session['user_email'] = created_user["email"]
            request.session['user_id'] = created_user["id"]
            request.session['remember_me'] = True
        await conn.close()
        if wants_json:
            return JSONResponse({"success": True, "redirect": "/"})
        return RedirectResponse(url="/", status_code=303)
    except PgIntegrityError:
        await conn.close()
        return fail("Email already exists" if lang == 'en' else "電郵已存在", field="email")
    except Exception as e:
        await conn.close()
        _builtins._original_print(f"[ERROR] Registration failed: {e}")
        return fail(
            "Service temporarily unavailable. Your account data remains in database; please try again."
            if lang == 'en'
            else "服務暫時不可用。帳號資料會保留喺資料庫，請稍後再試。",
            field="email",
            status_code=500,
        )

@app.get("/auth/google")
async def google_login(request: Request):
    """Redirect to Google's consent screen. 404s if Google sign-in isn't configured."""
    if not GOOGLE_LOGIN_ENABLED:
        raise HTTPException(status_code=404)
    redirect_uri = GOOGLE_REDIRECT_URI or str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    """Handle Google's redirect back: verify the ID token, then find-or-create
    the local user and log them in the same way /login does.

    Matching order: first by google_id (returning Google user), then by
    email (auto-link an existing password account — Google already verified
    ownership of that email), otherwise create a brand-new account with a
    random, never-typeable password hash.
    """
    if not GOOGLE_LOGIN_ENABLED:
        raise HTTPException(status_code=404)

    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(url="/login?error=google_failed", status_code=303)

    userinfo = token.get("userinfo") or {}
    google_id = userinfo.get("sub")
    email = (userinfo.get("email") or "").strip().lower()
    if not google_id or not email or not userinfo.get("email_verified"):
        return RedirectResponse(url="/login?error=google_failed", status_code=303)

    display_name = _CONTROL_CHAR_PATTERN.sub(" ", userinfo.get("name") or "")
    display_name = " ".join(display_name.split())[:50]

    conn = await get_db()
    c = conn.cursor()
    try:
        await db_execute(c, "SELECT id, email FROM users WHERE google_id = ?", (google_id,))
        user = c.fetchone()

        if not user:
            await db_execute(c, "SELECT id, email, google_id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            existing = c.fetchone()
            if existing and existing["google_id"]:
                # Email matches, but already linked to a different Google account.
                await conn.close()
                return RedirectResponse(url="/login?error=google_failed", status_code=303)
            if existing:
                await db_execute(c, "UPDATE users SET google_id = ?, auth_provider = 'google' WHERE id = ?", (google_id, existing["id"]))
                user = existing
            else:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                synthetic_password = hash_password(secrets.token_hex(32))
                await db_execute(
                    c,
                    "INSERT INTO users (email, password, username, google_id, auth_provider, created_at) VALUES (?, ?, ?, ?, 'google', ?)",
                    (email, synthetic_password, display_name or None, google_id, ts),
                )
                await db_execute(c, "SELECT id, email FROM users WHERE google_id = ?", (google_id,))
                user = c.fetchone()

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db_execute(c, "UPDATE users SET last_login = ? WHERE id = ?", (ts, user["id"]))
        await conn.commit()
        request.session['user_email'] = user["email"]
        request.session['user_id'] = user["id"]
        request.session['remember_me'] = True
    finally:
        await conn.close()

    return RedirectResponse(url="/", status_code=303)


@app.get("/forgot_password")
async def forgot_password(request: Request):
    return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

# ---------------------------------------------------------------------------
# Main Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    uid = get_user(request)
    if uid is None:
        return templates.TemplateResponse("login.html", tpl_context(request))
    return templates.TemplateResponse("chat.html", tpl_context(request))

_SAFE_REDIRECT_PATHS = {
    "/", "/chat", "/accessibility", "/hk_guide", "/login", "/register", "/profile",
}

def _safe_redirect_target(request: Request) -> str:
    """Resolve where to send the user back to after switching language.

    Uses the Referer header so the language switch keeps the user on the
    page they were viewing (e.g. hk_guide, accessibility) instead of always
    bouncing to /. Only same-origin, known app paths are honored to avoid
    open-redirect via a spoofed Referer header.
    """
    referer = request.headers.get("referer")
    if not referer:
        return "/"
    try:
        parsed = urlsplit(referer)
        if parsed.netloc and parsed.netloc != request.url.netloc:
            return "/"
        if parsed.path in _SAFE_REDIRECT_PATHS:
            return parsed.path
    except ValueError:
        pass
    return "/"

@app.get("/set_language/{lang}")
async def set_language(request: Request, lang: str):
    """Set user language preference, persist to database, and redirect back
    to the page the user was viewing (so switching language shows that same
    page, translated) instead of always bouncing to /chat."""
    if lang in ('en', 'zh-HK'):
        request.session['language'] = lang
        uid = get_user(request)
        if uid:
            conn = await get_db()
            c = conn.cursor()
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await db_insert_or_replace_preference(c, uid, 'language', lang, ts)
            await conn.commit()
            await conn.close()
    return RedirectResponse(url=_safe_redirect_target(request), status_code=303)

@app.get("/accessibility", response_class=HTMLResponse)
async def accessibility_mode(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("accessibility.html", tpl_context(request))

# ---------------------------------------------------------------------------
# Profile — display name + password
# ---------------------------------------------------------------------------
_CONTROL_CHAR_PATTERN = re.compile(r"[\r\n\t\x00-\x1f]")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    conn = await get_db()
    c = conn.cursor()
    await db_execute(c, "SELECT username, email FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    await conn.close()
    return templates.TemplateResponse(
        "profile.html",
        tpl_context(
            request,
            display_name=(user_row["username"] if user_row else None) or "",
            email=user_row["email"] if user_row else "",
        ),
    )


@app.post("/profile/name")
async def update_profile_name(request: Request, display_name: str = Form(...)):
    """Update the user's display name, shown in chat headers and used to
    let the AI address them by name (see call_ai's `display_name` param)."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    lang = get_lang(request)

    # Strip control characters and collapse whitespace — this value is later
    # interpolated directly into the LLM system prompt in call_ai(), so it
    # must never be able to smuggle in newlines or a fake "SYSTEM:" line.
    cleaned = _CONTROL_CHAR_PATTERN.sub(" ", display_name)
    cleaned = " ".join(cleaned.split())[:50]

    if not cleaned:
        return JSONResponse(
            {"success": False, "field": "display_name", "message": "Please enter a name" if lang == 'en' else "請輸入名稱"},
            status_code=400,
        )

    conn = await get_db()
    c = conn.cursor()
    await db_execute(c, "UPDATE users SET username = ? WHERE id = ?", (cleaned, uid))
    await conn.commit()
    await conn.close()
    return JSONResponse({"success": True, "display_name": cleaned, "message": "Name updated" if lang == 'en' else "名稱已更新"})


@app.post("/profile/password")
async def update_profile_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_new_password: str = Form(...),
):
    """Change the user's password, gated on confirming the current one."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    lang = get_lang(request)

    def fail(message: str, field: str, status_code: int = 400):
        return JSONResponse({"success": False, "field": field, "message": message}, status_code=status_code)

    current_password = current_password.strip()
    new_password = new_password.strip()
    confirm_new_password = confirm_new_password.strip()

    conn = await get_db()
    c = conn.cursor()
    await db_execute(c, "SELECT password FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    if not user_row or not verify_password(current_password, user_row["password"]):
        await conn.close()
        return fail("Current password is incorrect" if lang == 'en' else "現時密碼不正確", field="current_password")

    is_valid_password, _ = validate_password_strength(new_password)
    if not is_valid_password:
        await conn.close()
        return fail("Password must be at least 8 characters" if lang == 'en' else "密碼最少需要 8 個字元", field="new_password")

    if new_password != confirm_new_password:
        await conn.close()
        return fail("Passwords do not match" if lang == 'en' else "密碼唔一致", field="confirm_new_password")

    await db_execute(c, "UPDATE users SET password = ? WHERE id = ?", (hash_password(new_password), uid))
    await conn.commit()
    await conn.close()
    return JSONResponse({"success": True, "message": "Password updated" if lang == 'en' else "密碼已更新"})

async def _get_or_create_active_conversation(cursor, user_id: int, lang: str, requested_id: Optional[int]) -> int:
    """Resolve which conversation a new message belongs to.

    Trusts `requested_id` only if it exists, belongs to this user, and isn't
    deleted; otherwise falls back to the user's most recently updated
    conversation for this language, creating one if they have none yet. This
    keeps callers that don't know about conversations (quick-action buttons
    that POST to /get_response directly) working without any changes.
    """
    if requested_id is not None:
        await db_execute(
            cursor,
            "SELECT id FROM conversations WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (requested_id, user_id),
        )
        if cursor.fetchone():
            return requested_id

    await db_execute(
        cursor,
        "SELECT id FROM conversations WHERE user_id = ? AND lang = ? AND is_deleted = FALSE ORDER BY updated_at DESC LIMIT 1",
        (user_id, lang),
    )
    row = cursor.fetchone()
    if row:
        return row["id"]

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db_execute(
        cursor,
        "INSERT INTO conversations (user_id, lang, created_at, updated_at) VALUES (?, ?, ?, ?) RETURNING id",
        (user_id, lang, ts, ts),
    )
    return cursor.fetchone()["id"]


# ---------------------------------------------------------------------------
# Chat Response — the core message handler
#
# Accepts free-text input from the user, checks for special command
# prefixes (reminders, games, preferences), and falls through to the
# Tencent Hunyuan LLM for general conversation.
# ---------------------------------------------------------------------------
@app.post("/get_response")
async def get_response(request: Request, msg: str = Form(...), conversation_id: Optional[int] = Form(None)):
    """Process user message and return AI/command response."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"response": "Please log in."}, status_code=401)

    lang = get_lang(request)
    user_input_original = msg.strip()
    user_input_lower = user_input_original.lower()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = await get_db()
    c = conn.cursor()

    # conversation_id is optional so older/other callers (voice shortcuts,
    # the reminder-delete quick action) keep working unchanged — they just
    # land in the user's most recent conversation instead of a specific one.
    conversation_id = await _get_or_create_active_conversation(c, uid, lang, conversation_id)

    # Store user message
    await db_execute(
        c,
        "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, FALSE, ?, FALSE, ?)",
        (uid, lang, timestamp, user_input_original, conversation_id),
    )
    # Auto-title from the first message in this conversation; COALESCE makes
    # this a no-op once a title already exists.
    preview_title = user_input_original.replace("\n", " ").replace("\r", " ").strip()[:40]
    await db_execute(
        c,
        "UPDATE conversations SET title = COALESCE(title, ?), updated_at = ? WHERE id = ?",
        (preview_title or None, timestamp, conversation_id),
    )
    await conn.commit()

    response = ""

    # ---- Check for guide-helper trigger keywords ----
    guide_triggers_zh = ['教', '點用', '唔明', '幫教']
    guide_triggers_en = ['teach', 'how to use', 'help me', 'guide']
    is_guide_trigger = False
    if lang == 'zh-HK':
        is_guide_trigger = any(t in user_input_original for t in guide_triggers_zh)
    else:
        is_guide_trigger = any(t in user_input_lower for t in guide_triggers_en)

    if is_guide_trigger:
        if lang == 'zh-HK':
            response = ("📖 你可以撳右下角嘅「？」按鈕打開操作指引！入面有所有功能嘅使用方法。\n\n"
                        "簡單指令：\n"
                        "• 打字或者講嘢同我傾偈\n"
                        "• 「設置提醒 食藥 09:00」設提醒\n"
                        "• 「玩遊戲」開始問答遊戲\n"
                        "• 撳🔍按鈕搜尋網頁\n"
                        "• 撳📎按鈕上傳檔案")
        else:
            response = ("📖 Click the '?' button at the bottom-right to open the Operation Guide!\n\n"
                        "Quick commands:\n"
                        "• Type or speak to chat with me\n"
                        "• 'set reminder take medicine 09:00' to set a reminder\n"
                        "• 'play game' to start a quiz\n"
                        "• Click 🔍 button for web search\n"
                        "• Click 📎 button to upload files")

    # ---- Reminder Commands ----
    elif user_input_lower.startswith("set reminder") or user_input_lower.startswith("設置提醒"):
        if user_input_lower.startswith("設置提醒"):
            parts = user_input_original.split()
            if len(parts) >= 3 and ':' in parts[-1]:
                time_str = parts[-1]
                label = ' '.join(parts[1:-1])
            else:
                response = "格式：設置提醒 [活動] [HH:MM]"
                await db_execute(c, "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, TRUE, ?, FALSE, ?)", (uid, lang, timestamp, response, conversation_id))
                await conn.commit(); await conn.close()
                return JSONResponse({"response": response})
        else:
            parts = user_input_lower.split()
            if len(parts) >= 4 and len(parts[-1]) == 5 and parts[-1][2] == ':':
                time_str = parts[-1]
                label = ' '.join(parts[2:-1])
            else:
                response = "Usage: set reminder [activity] [HH:MM]"
                await db_execute(c, "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, TRUE, ?, FALSE, ?)", (uid, lang, timestamp, response, conversation_id))
                await conn.commit(); await conn.close()
                return JSONResponse({"response": response})

        try:
            # Validate time format (HH:MM) and parse hours/minutes
            h, m = map(int, time_str.split(':'))
            # Ensure valid 24-hour format (0-23 for hours, 0-59 for minutes)
            if 0 <= h <= 23 and 0 <= m <= 59:
                await db_execute(
                    c,
                    "INSERT INTO reminders (user_id, label, reminder_time, is_active, created_at) VALUES (?, ?, ?, TRUE, ?)",
                    (uid, label, time_str, timestamp),
                )
                await conn.commit()
                response = f"提醒已設置：{label}，時間 {time_str}" if lang == 'zh-HK' else f"Reminder set: {label} at {time_str}"
            else:
                response = "時間無效。請用24小時格式 HH:MM" if lang == 'zh-HK' else "Invalid time. Use 24-hour format HH:MM"
        except (ValueError, IndexError):
            # Handle malformed time strings (e.g., invalid separators, non-numeric values)
            response = "時間格式錯誤。請用 HH:MM" if lang == 'zh-HK' else "Invalid time format. Use HH:MM"

    elif user_input_lower.startswith("delete reminder") or user_input_lower.startswith("刪除提醒"):
        if user_input_lower.startswith("刪除提醒"):
            parts = user_input_original.split(maxsplit=1)
            label = parts[1] if len(parts) == 2 else None
        else:
            parts = user_input_lower.split(maxsplit=2)
            label = parts[2] if len(parts) == 3 else None
        if label:
            await db_execute(c, "DELETE FROM reminders WHERE user_id = ? AND label = ?", (uid, label))
            if _safe_rowcount(c) > 0:
                response = f"已刪除提醒：{label}" if lang == 'zh-HK' else f"Deleted reminder: {label}"
            else:
                response = "搵唔到呢個提醒。" if lang == 'zh-HK' else "No reminder found with that name."
            await conn.commit()
        else:
            response = "格式：刪除提醒 [活動]" if lang == 'zh-HK' else "Usage: delete reminder [activity]"

    # ---- Preference Commands ----
    elif user_input_lower.startswith("set preference"):
        parts = user_input_lower.split(maxsplit=4)
        if len(parts) >= 4:
            key, value = parts[2], parts[3]
            await db_insert_or_replace_preference(c, uid, key, value, timestamp)
            await conn.commit()
            response = f"Preference updated: {key} = {value}"
        else:
            response = "Usage: set preference [key] [value]"

    # ---- Quiz Game ----
    else:
        game_defaults = {
            'is_game_mode': False,
            'current_index': 0,
            'current_question': None,
            'correct_answer': None,
            'score': 0,
            'lang': lang,
        }

        # Session-backed game state is more reliable than process memory and
        # avoids accidental mode loss across reloads or worker boundaries.
        stored_game = request.session.get('game_state')
        if isinstance(stored_game, dict):
            game = {**game_defaults, **stored_game}
        else:
            game = {**game_defaults, **user_game_states.get(uid, {})}

        game_lang = game.get('lang', lang)
        # Treat any zh-* language code as Chinese so users with 'zh',
        # 'zh-CN', or 'zh-HK' preferences get the Chinese question set.
        active_questions = questions_zh if (isinstance(game_lang, str) and game_lang.startswith('zh')) else questions

        def _persist_game_state() -> None:
            request.session['game_state'] = game
            user_game_states[uid] = game

        game_trigger = user_input_lower in ["play game", "玩遊戲", "玩游戏"]
        exit_trigger = user_input_lower in ["exit game", "退出遊戲", "退出游戏"]
        answer_prefixes = ["answer ", "答案 ", "答案：", "答案:", "回答 ", "答 "]
        answer_only_tokens = {"answer", "答案", "回答", "答"}

        # If the session lost game state but the last bot message was a quiz
        # question (e.g., page reload or worker switch), detect it from the
        # most recent bot message in chat_history and restore game mode.
        if not game.get('is_game_mode'):
            try:
                await db_execute(
                    c,
                    "SELECT message FROM chat_history WHERE user_id = ? AND lang = ? AND is_bot = TRUE ORDER BY timestamp DESC LIMIT 1",
                    (uid, game_lang),
                )
                last_bot = c.fetchone()
                last_text = (last_bot[0] if isinstance(last_bot, (list, tuple)) else (last_bot.get('message') if last_bot else '')) if last_bot else ''
            except Exception:
                last_text = ''
            if last_text:
                for idx, q in enumerate(active_questions):
                    if q['question'] and q['question'] in last_text:
                        game['is_game_mode'] = True
                        game['current_index'] = idx
                        game['current_question'] = q['question']
                        game['correct_answer'] = q['answer']
                        _persist_game_state()
                        break

        if game_trigger and not game['is_game_mode']:
            game['is_game_mode'] = True
            game['current_index'] = 0
            game['score'] = 0
            game['lang'] = lang
            q = active_questions[0]
            game['current_question'] = q["question"]
            game['correct_answer'] = q["answer"]
            if lang == 'zh-HK':
                response = f"開始玩喇！一共有{len(active_questions)}條問題。分數：0。第一條問題：{game['current_question']}"
            else:
                response = f"Let's play! You have {len(active_questions)} questions. Current score: 0. First question: {game['current_question']}"
            _persist_game_state()

        elif exit_trigger and game['is_game_mode']:
            game['is_game_mode'] = False
            if lang == 'zh-HK':
                response = f"遊戲結束！你答啱咗{game['score']}條（總共{game['current_index']}條）。"
            else:
                response = f"Game stopped. You got {game['score']} out of {game['current_index']} correct so far!"
            _persist_game_state()

        elif game['is_game_mode']:
            answer_text = user_input_original.strip()
            answer_text_lower = user_input_lower.strip()
            for prefix in answer_prefixes:
                if answer_text_lower.startswith(prefix):
                    answer_text = answer_text[len(prefix):].strip()
                    answer_text_lower = answer_text.lower()
                    break

            if answer_text_lower in answer_only_tokens or not answer_text:
                if lang == 'zh-HK':
                    response = f"請輸入答案內容先喔。呢條問題係：{game['current_question']}"
                else:
                    response = f"Please type your answer after 'answer'. Current question: {game['current_question']}"
                _persist_game_state()
            elif _is_quiz_answer_correct(answer_text, game['correct_answer']):
                game['score'] += 1
                response = f"啱咗！分數：{game['score']}" if lang == 'zh-HK' else f"Correct! Score: {game['score']}"
            else:
                if lang == 'zh-HK':
                    response = f"唔啱呀，答案係{game['correct_answer']}。分數：{game['score']}"
                else:
                    response = f"Incorrect. The answer was {game['correct_answer']}. Score: {game['score']}"
            if answer_text_lower not in answer_only_tokens and answer_text:
                game['current_index'] += 1
                if game['current_index'] == len(active_questions):
                    if lang == 'zh-HK':
                        response += f"\n遊戲完成！你答啱咗{game['score']}條（總共{len(active_questions)}條）。叻叻！"
                    else:
                        response += f"\nGame over! You successfully answered {game['score']} out of {len(active_questions)} questions correctly."
                    game['is_game_mode'] = False
                else:
                    q = active_questions[game['current_index']]
                    game['current_question'] = q["question"]
                    game['correct_answer'] = q["answer"]
                    if lang == 'zh-HK':
                        response += f" 下一條問題：{q['question']}"
                    else:
                        response += f" Next question: {q['question']}"
                _persist_game_state()

        elif user_input_lower.startswith("answer") or user_input_lower.startswith("答案") or user_input_lower.startswith("回答"):
            response = (
                "你未開始遊戲呀，請先輸入「玩遊戲」。" if lang == 'zh-HK'
                else "You're not in a game yet. Type 'play game' first."
            )

        # ---- Normal AI Chat ----
        else:
            await db_execute(c, "SELECT username FROM users WHERE id = ?", (uid,))
            user_row = c.fetchone()
            display_name = user_row["username"] if user_row else None
            response = await call_ai(user_input_original, uid, lang, display_name=display_name)

    # Store bot response
    await db_execute(
        c,
        "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, TRUE, ?, FALSE, ?)",
        (uid, lang, timestamp, response, conversation_id),
    )

    # Keep recent history stable across Vercel/local/mobile by pruning oldest rows.
    await prune_user_chat_history(c, conversation_id)
    await conn.commit()
    await conn.close()

    return JSONResponse({"response": response})

# ---------------------------------------------------------------------------
# Voice Transcription
# ---------------------------------------------------------------------------
async def _transcribe_with_hf_whisper(content: bytes) -> str:
    """Call Hugging Face Inference API (Whisper large-v3). Raises on failure."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            HF_WHISPER_URL,
            headers={
                "Authorization": f"Bearer {HF_API_KEY}",
                "Content-Type": "audio/wav",
            },
            content=content,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "text" in data:
            return data["text"].strip()
        raise ValueError(f"Unexpected Whisper response: {data}")


def _transcribe_with_google_fallback(content: bytes, language: str) -> str:
    """Legacy SpeechRecognition + Google Web Speech backend fallback."""
    if sr is None:
        raise RuntimeError("Server STT dependency missing (SpeechRecognition).")
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(content)) as source:
        audio_data = recognizer.record(source)
    return recognizer.recognize_google(audio_data, language=language).strip()


@app.post("/transcribe")
async def transcribe_audio(request: Request, audio: UploadFile = File(...), lang: str = Form("en-US")):
    """Server-side STT. Primary engine: Whisper large-v3 (Hugging Face Inference
    API). Falls back to Google Web Speech (via SpeechRecognition) if no HF key
    is configured or the HF call fails.
    """
    if get_user(request) is None:
        return JSONResponse({"text": "", "error": "Not authenticated"}, status_code=401)

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_TRANSCRIBE_UPLOAD_BYTES:
        return JSONResponse({"text": "", "error": "Audio file too large."}, status_code=413)
    if audio.content_type and not audio.content_type.startswith("audio/"):
        return JSONResponse({"text": "", "error": "Expected an audio file."}, status_code=415)

    language = (lang or get_lang(request) or "en").strip()
    lang_map = {
        "en": "en-US",
        "en-us": "en-US",
        "zh": "zh-HK",
        "zh-hk": "zh-HK",
        "zh_HK": "zh-HK",
    }
    language = lang_map.get(language.lower(), language)

    content = await audio.read()
    if not content:
        return JSONResponse({"text": "", "error": "Empty audio payload."}, status_code=400)
    if len(content) > MAX_TRANSCRIBE_UPLOAD_BYTES:
        return JSONResponse({"text": "", "error": "Audio file too large."}, status_code=413)

    if HF_API_KEY:
        try:
            text = await _transcribe_with_hf_whisper(content)
            if text:
                return JSONResponse({"text": text, "engine": HF_WHISPER_MODEL})
            return JSONResponse(
                {"text": "", "error": get_text("no_speech_detected", get_lang(request))},
                status_code=422,
            )
        except Exception as e:
            _builtins._original_print(f"[STT] Whisper (HF) error, falling back: {e}")

    if sr is None:
        return JSONResponse(
            {"text": "", "error": "Server STT dependency missing (SpeechRecognition)."},
            status_code=503,
        )

    try:
        text = _transcribe_with_google_fallback(content, language)
        return JSONResponse({"text": text, "engine": "google-web-speech"})
    except sr.UnknownValueError:
        return JSONResponse(
            {"text": "", "error": get_text("no_speech_detected", get_lang(request))},
            status_code=422,
        )
    except sr.RequestError as e:
        _builtins._original_print(f"[STT] upstream request error: {e}")
        return JSONResponse(
            {"text": "", "error": get_text("error_network", get_lang(request))},
            status_code=503,
        )
    except Exception as e:
        _builtins._original_print(f"[STT] transcribe error: {e}")
        return JSONResponse(
            {"text": "", "error": get_text("error_voice", get_lang(request))},
            status_code=500,
        )

# ---------------------------------------------------------------------------
# Reminder Management endpoints (AJAX)
# ---------------------------------------------------------------------------
@app.post("/register_device")
async def register_device(request: Request):
    try:
        data = await request.json()
        token = data.get("device_token")
        uid = get_user(request)
        if uid and token:
            # In a real setup, save this `token` to the database for this user
            print(f"[Push] Registered device token for {uid}: {token}")
            return JSONResponse({"status": "ok"})
    except:
        pass
    return JSONResponse({"status": "ignored"})

@app.post("/deactivate_reminder")
async def deactivate_reminder(request: Request, label: str = Form(...)):
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False}, status_code=401)
    conn = await get_db()
    c = conn.cursor()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db_execute(c, "UPDATE reminders SET is_active = FALSE, updated_at = ? WHERE user_id = ? AND label = ?", (ts, uid, label))
    await conn.commit()
    await conn.close()
    return JSONResponse({"success": True})

@app.get("/get_reminders")
async def get_reminders(request: Request):
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"reminders": []})
    conn = await get_db()
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    await db_execute(
        c,
        "SELECT label, reminder_time, is_active FROM reminders WHERE user_id = ? AND DATE(created_at) = ? ORDER BY created_at DESC",
        (uid, today),
    )
    reminders = [{"label": r["label"], "time": r["reminder_time"], "active": bool(r["is_active"])} for r in c.fetchall()]
    await conn.close()
    return JSONResponse({"reminders": reminders})

async def _load_conversation_messages(cursor, conn, conversation_id: int, lang: str) -> list:
    """Shared history-loading logic for one conversation.

    Extracted so both the legacy `/get_chat_history` endpoint and the new
    per-conversation endpoint return identical shapes and share the
    stale-greeting cleanup behaviour.
    """
    await db_execute(
        cursor,
        "SELECT id, timestamp, is_bot, message FROM chat_history WHERE conversation_id = ? AND is_deleted = FALSE ORDER BY timestamp",
        (conversation_id,),
    )
    rows = cursor.fetchall()

    # A lone bot-authored auto-greeting isn't real conversation content —
    # if it's stuck showing a different language's greeting text (e.g. it
    # was written before the user ever switched language), soft-delete it
    # so it gets recomputed live in the *current* language below, instead
    # of staying frozen in whatever language it was first shown in.
    current_welcome = get_text("welcome_chat", lang)
    if len(rows) == 1 and rows[0]["is_bot"]:
        all_welcome_variants = {get_text("welcome_chat", l) for l in TRANSLATIONS}
        if rows[0]["message"] in all_welcome_variants and rows[0]["message"] != current_welcome:
            await db_execute(cursor, "UPDATE chat_history SET is_deleted = TRUE WHERE id = ?", (rows[0]["id"],))
            await conn.commit()
            rows = []

    history = [
        {
            "timestamp": _json_timestamp(r["timestamp"]),
            "sender": "bot" if r["is_bot"] else "user",
            "message": r["message"],
        }
        for r in rows
    ]

    if not history:
        # Recomputed live (not persisted) so it always matches the
        # current UI language, even across repeated language switches
        # before the user ever sends a real message.
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history = [{"timestamp": ts, "sender": "bot", "message": current_welcome}]

    return history


@app.get("/get_chat_history")
async def get_chat_history(request: Request):
    """Legacy: get history for the user's most recent conversation.

    Kept for callers that don't know about conversations yet (the
    accessibility-mode chat page) — resolves to the same "most recent, or
    create one" conversation that a conversation_id-less /get_response call
    would land in, so both stay in sync.
    """
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"history": []})
    lang = get_lang(request)
    conn = None
    try:
        conn = await get_db()
        c = conn.cursor()
        conversation_id = await _get_or_create_active_conversation(c, uid, lang, None)
        await conn.commit()
        history = await _load_conversation_messages(c, conn, conversation_id, lang)
        return JSONResponse({"history": history})
    except Exception as e:
        # Graceful degradation for transient DB/network failures.
        _builtins._original_print(f"[CHAT_HISTORY] fallback due to DB error: {e}")
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return JSONResponse({"history": [{"timestamp": ts, "sender": "bot", "message": get_text("welcome_chat", lang)}], "degraded": True})
    finally:
        if conn is not None:
            await conn.close()


@app.get("/conversations")
async def list_conversations(request: Request):
    """List the current user's conversations for the sidebar, newest first."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"conversations": []})
    lang = get_lang(request)
    conn = await get_db()
    c = conn.cursor()
    await db_execute(
        c,
        "SELECT id, title, updated_at, pinned, tag FROM conversations "
        "WHERE user_id = ? AND lang = ? AND is_deleted = FALSE "
        "ORDER BY pinned DESC, updated_at DESC",
        (uid, lang),
    )
    conversations = [
        {
            "id": r["id"],
            "title": r["title"] or get_text("new_conversation", lang),
            "updated_at": _json_timestamp(r["updated_at"]),
            "pinned": bool(r["pinned"]),
            "tag": r["tag"],
        }
        for r in c.fetchall()
    ]
    await conn.close()
    return JSONResponse({"conversations": conversations})


@app.post("/conversations/{conversation_id}/pin")
async def toggle_conversation_pin(request: Request, conversation_id: int):
    """Flip a conversation's pinned state; pinned ones sort first."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    conn = await get_db()
    try:
        c = conn.cursor()
        await db_execute(
            c,
            "SELECT pinned FROM conversations WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (conversation_id, uid),
        )
        row = c.fetchone()
        if not row:
            return JSONResponse({"error": "not found"}, status_code=404)
        new_pinned = not row["pinned"]
        await db_execute(c, "UPDATE conversations SET pinned = ? WHERE id = ?", (new_pinned, conversation_id))
        await conn.commit()
        return JSONResponse({"pinned": new_pinned})
    finally:
        await conn.close()


@app.post("/conversations/{conversation_id}/tag")
async def set_conversation_tag(request: Request, conversation_id: int, tag: str = Form("")):
    """Set (or clear, with an empty value) a conversation's category tag."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    tag = tag.strip()
    if tag and tag not in CONVERSATION_TAGS:
        return JSONResponse({"error": "invalid tag"}, status_code=400)
    conn = await get_db()
    try:
        c = conn.cursor()
        await db_execute(
            c,
            "UPDATE conversations SET tag = ? WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (tag or None, conversation_id, uid),
        )
        found = _safe_rowcount(c) > 0
        await conn.commit()
        if not found:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"tag": tag or None})
    finally:
        await conn.close()


@app.post("/conversations/{conversation_id}/title")
async def rename_conversation(request: Request, conversation_id: int, title: str = Form(...)):
    """Rename a conversation. An empty result after cleanup falls back to
    the auto-generated title (first-message text) instead of storing blank."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    lang = get_lang(request)
    cleaned = _CONTROL_CHAR_PATTERN.sub(" ", title)
    cleaned = " ".join(cleaned.split())[:100]
    conn = await get_db()
    try:
        c = conn.cursor()
        await db_execute(
            c,
            "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (cleaned or None, conversation_id, uid),
        )
        found = _safe_rowcount(c) > 0
        await conn.commit()
        if not found:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"title": cleaned or get_text("new_conversation", lang)})
    finally:
        await conn.close()


@app.get("/history", response_class=HTMLResponse)
async def conversation_history_page(request: Request):
    """Dedicated page for browsing, pinning, and tagging all conversations —
    the sidebar only keeps a "new conversation" shortcut once this exists."""
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "conversation_history.html",
        tpl_context(request, conversation_tags=CONVERSATION_TAGS),
    )


@app.post("/conversations/new")
async def create_conversation(request: Request):
    """Start a new, empty conversation and return its id."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    lang = get_lang(request)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = await get_db()
    c = conn.cursor()
    await db_execute(
        c,
        "INSERT INTO conversations (user_id, lang, created_at, updated_at) VALUES (?, ?, ?, ?) RETURNING id",
        (uid, lang, ts, ts),
    )
    new_id = c.fetchone()["id"]
    # cleanup_old_conversations() (the batch job that normally enforces this
    # cap) only runs from run_periodic_tasks(), which is explicitly skipped
    # on Vercel — so on this deployment target nothing else ever trims a
    # user's conversation count. Enforce the same cap inline, per-write,
    # instead of relying on a background loop that doesn't run here.
    await db_execute(
        c,
        "WITH ranked AS ("
        "  SELECT id, ROW_NUMBER() OVER (ORDER BY updated_at DESC, id DESC) AS rn"
        "  FROM conversations WHERE user_id = ? AND lang = ? AND is_deleted = FALSE"
        ") UPDATE conversations SET is_deleted = TRUE WHERE id IN (SELECT id FROM ranked WHERE rn > ?)",
        (uid, lang, CONVERSATION_MAX_PER_LANG),
    )
    await conn.commit()
    await conn.close()
    return JSONResponse({"conversation_id": new_id})


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(request: Request, conversation_id: int):
    """Get the message history for one specific conversation."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"history": []}, status_code=401)
    lang = get_lang(request)
    conn = None
    try:
        conn = await get_db()
        c = conn.cursor()
        # Ownership check — a conversation_id belonging to another user (or a
        # deleted one) is treated as not found rather than leaking its rows.
        await db_execute(c, "SELECT id FROM conversations WHERE id = ? AND user_id = ? AND is_deleted = FALSE", (conversation_id, uid))
        if not c.fetchone():
            return JSONResponse({"history": [], "error": "not found"}, status_code=404)
        history = await _load_conversation_messages(c, conn, conversation_id, lang)
        return JSONResponse({"history": history})
    except Exception as e:
        _builtins._original_print(f"[CONVERSATIONS] fallback due to DB error: {e}")
        return JSONResponse({"history": [], "degraded": True})
    finally:
        if conn is not None:
            await conn.close()


@app.get("/health/db")
async def health_db(request: Request):
    """Database connectivity health check: verify PostgreSQL is accessible.

    Returns a bare {"ok": bool} to unauthenticated callers — infra details
    (hostname, raw exception text) are only included for a logged-in caller,
    since this is a public repo/deployment and that's reconnaissance-useful
    info to hand an anonymous caller for free.
    """
    uid = get_user(request)
    initialized = await ensure_db_initialized(strict=False)
    conn = None
    try:
        conn = await get_db()
        c = conn.cursor()
        await c.execute("SELECT 1")
        _ = c.fetchone()
        body = {"ok": True}
        if uid is not None:
            body.update({
                "backend": _RUNTIME_DB_BACKEND,
                "configured_backend": DB_BACKEND,
                "db_initialized": initialized,
                "db_init_error": _db_init_error,
                "db_url_source": _DB_URL_SOURCE,
                "db_runtime_label": _DB_RUNTIME_LABEL,
                "db_hostname": _DB_HOSTNAME,
                "db_hostaddr": _DB_HOSTADDR,
                "db_last_pg_attempts": _DB_LAST_PG_ATTEMPTS,
            })
        return JSONResponse(body)
    except Exception as e:
        body = {"ok": False}
        if uid is not None:
            body.update({
                "backend": _RUNTIME_DB_BACKEND,
                "configured_backend": DB_BACKEND,
                "db_initialized": initialized,
                "db_init_error": _db_init_error,
                "db_url_source": _DB_URL_SOURCE,
                "db_runtime_label": _DB_RUNTIME_LABEL,
                "db_hostname": _DB_HOSTNAME,
                "db_hostaddr": _DB_HOSTADDR,
                "db_last_pg_attempts": _DB_LAST_PG_ATTEMPTS,
                "error": str(e),
            })
        return JSONResponse(body, status_code=500)
    finally:
        if conn is not None:
            await conn.close()


@app.get("/health")
async def health():
    """Basic process-level health probe for uptime checks — deliberately
    minimal (no infra details) since this endpoint is public/unauthenticated
    by design. Use /health/db while logged in for the verbose diagnostic."""
    return JSONResponse({"ok": True, "service": "the-listening-tree"})

# ---------------------------------------------------------------------------
# HK Public Holidays 2025-2027
#
# Static dataset consumed by FullCalendar on the client side.
# ---------------------------------------------------------------------------
HK_HOLIDAYS = [
    # 2025
    {"date": "2025-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2025-01-29", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2025-01-30", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2025-01-31", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2025-04-04", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2025-04-18", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2025-04-19", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2025-04-21", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2025-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2025-05-05", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2025-05-31", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2025-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2025-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2025-10-07", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2025-10-29", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2025-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2025-12-26", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
    # 2026
    {"date": "2026-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2026-02-17", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2026-02-18", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2026-02-19", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2026-04-03", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2026-04-04", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2026-04-05", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2026-04-06", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2026-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2026-05-24", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2026-06-19", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2026-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2026-09-26", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2026-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2026-10-17", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2026-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2026-12-26", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
    # 2027
    {"date": "2027-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2027-02-06", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2027-02-07", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2027-02-08", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2027-03-26", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2027-03-27", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2027-03-29", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2027-04-05", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2027-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2027-05-13", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2027-06-09", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2027-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2027-09-16", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2027-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2027-10-08", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2027-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2027-12-27", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
]

@app.get("/get_hk_holidays")
async def get_hk_holidays(request: Request):
    """Return HK public holidays for FullCalendar."""
    lang = get_lang(request)
    events = []
    for h in HK_HOLIDAYS:
        events.append({
            "title": h["name_zh"] if lang == "zh-HK" else h["name_en"],
            "start": h["date"],
            "allDay": True,
            "color": "#E07A5F",
            "textColor": "#FFFFFF",
            "classNames": ["holiday-event"],
        })
    return JSONResponse({"holidays": events})

# ---------------------------------------------------------------------------
# HK News — proxy endpoint (NewsAPI with in-memory cache)
#
# Falls back to hardcoded placeholder articles when no API key is set.
# Cache TTL: 30 minutes.
# ---------------------------------------------------------------------------
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '')
_news_cache = {"data": None, "timestamp": 0, "lang": None}

async def fetch_hk_news(lang: str = 'en'):
    """Fetch HK news from NewsAPI; cache for 30 min."""
    import time
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["timestamp"]) < 1800 and _news_cache["lang"] == lang:
        return _news_cache["data"]

    articles = []

    # Try NewsAPI if key available
    if NEWS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params={"country": "hk", "pageSize": 8, "apiKey": NEWS_API_KEY}
                )
                resp.raise_for_status()
                data = resp.json()
                for a in data.get("articles", [])[:8]:
                    articles.append({
                        "title": a.get("title", ""),
                        "description": a.get("description", "") or "",
                        "url": a.get("url", "#"),
                        "source": a.get("source", {}).get("name", ""),
                        "publishedAt": a.get("publishedAt", ""),
                        "image": a.get("urlToImage", ""),
                    })
        except Exception as e:
            print(f"[News] NewsAPI error: {e}")

    # Fallback: use hardcoded recent HK news placeholders
    if not articles:
        if lang == 'zh-HK':
            articles = [
                {"title": "天文台預測未來數日天氣回暖", "description": "天文台表示，受暖濕氣流影響，未來數日氣溫將回升至22-25度，市民外出請注意添減衣物。", "url": "#", "source": "天文台", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "港鐵新線路規劃公佈", "description": "政府今日公佈港鐵新線路規劃詳情，包括北環線及其延伸段，預計2030年完工通車。", "url": "#", "source": "政府新聞處", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "長者醫療券使用範圍擴大", "description": "政府宣佈長者醫療券使用範圍將進一步擴大，涵蓋更多醫療服務項目，惠及更多長者。", "url": "#", "source": "衛生署", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "沙田區社區活動日即將舉行", "description": "沙田區議會將於下週末舉辦社區活動日，設有健康檢查、興趣班及長者關懷活動。", "url": "#", "source": "區議會", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "本港今日天氣晴朗乾燥", "description": "天文台錄得今日最高氣溫23度，天氣晴朗乾燥，適合戶外活動。", "url": "#", "source": "天文台", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
            ]
        else:
            articles = [
                {"title": "HK Observatory forecasts warmer weather ahead", "description": "The Observatory expects temperatures to rise to 22-25°C over the next few days due to warm moist airflow.", "url": "#", "source": "HK Observatory", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "MTR new rail line planning announced", "description": "The government today released details of new MTR rail line planning, including the Northern Link and extensions, expected to be completed by 2030.", "url": "#", "source": "GovHK", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Elderly healthcare voucher scope expanded", "description": "The government announced an expansion of the elderly healthcare voucher scheme to cover more medical services.", "url": "#", "source": "Dept of Health", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Sha Tin community event day coming up", "description": "The Sha Tin District Council will host a community event day next weekend featuring health checks and elderly care activities.", "url": "#", "source": "District Council", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Fine and dry weather in Hong Kong today", "description": "The Observatory recorded a high of 23°C today. Fine and dry weather, suitable for outdoor activities.", "url": "#", "source": "HK Observatory", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
            ]

    _news_cache["data"] = articles
    _news_cache["timestamp"] = now
    _news_cache["lang"] = lang
    return articles

@app.get("/get_news")
async def get_news(request: Request):
    """Return HK local news articles."""
    lang = get_lang(request)
    articles = await fetch_hk_news(lang)
    return JSONResponse({"articles": articles})


# ---------------------------------------------------------------------------
# HK Local Guide — Food, Shopping, Entertainment, Events
#
# Curated dataset of elderly-friendly HK local attractions with live
# refresh capability.  Data is cached for 30 minutes and can be force-
# refreshed from the client.  Each item has bilingual content.
# ---------------------------------------------------------------------------
_hk_guide_cache: dict = {"data": None, "timestamp": 0, "lang": None}

# Curated HK local guide data (bilingual)
HK_GUIDE_DATA = {
    "en": [
        # ---- FOOD ----
        {
            "category": "food",
            "name": "Tim Ho Wan — Dim Sum",
            "short_desc": "World's cheapest Michelin-star dim sum. Famous for baked BBQ pork buns.",
            "full_desc": "Tim Ho Wan is the most affordable Michelin-starred restaurant in the world. Known for their signature baked BBQ pork buns with a crispy, sweet top crust. The dim sum menu is extensive and everything is freshly made. Perfect for a casual, affordable fine-dining experience. Multiple branches across Hong Kong.",
            "location": "Sham Shui Po, Mong Kok, Central (multiple branches)",
            "price_range": "HK$50–150 per person",
            "hours": "10:00 AM – 9:30 PM daily",
            "transport": "MTR Sham Shui Po Station Exit B2 (original branch)",
            "elderly_friendly": True,
            "tips": ["Go early to avoid long queues", "Try the baked BBQ pork buns — their signature dish", "Most branches have elevator access"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Mak's Noodle — Wonton Noodles",
            "short_desc": "Legendary wonton noodles since 1920s. Thin, springy noodles with shrimp wontons.",
            "full_desc": "A Hong Kong institution for nearly 100 years, Mak's Noodle serves some of the best wonton noodles in the city. The hand-pulled noodles are thin and springy, served in a clear shrimp broth with plump shrimp wontons. Simple, affordable, and deeply satisfying.",
            "location": "Wellington Street, Central",
            "price_range": "HK$40–80 per person",
            "hours": "11:00 AM – 8:00 PM daily",
            "transport": "MTR Central Station Exit D2, 5 min walk",
            "elderly_friendly": True,
            "tips": ["Small portions — perfect for trying multiple dishes", "Cash preferred at some branches", "Air-conditioned seating available"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Tai Cheong Bakery — Egg Tarts",
            "short_desc": "Hong Kong's most famous egg tarts. Flaky crust, silky custard filling.",
            "full_desc": "Tai Cheong Bakery has been making egg tarts since 1954. The last British Governor Chris Patten was a loyal customer, earning them the nickname 'Governor's egg tarts'. The pastry has a perfectly flaky crust with smooth, lightly sweet egg custard. A must-try Hong Kong classic.",
            "location": "Lyndhurst Terrace, Central (original); multiple branches",
            "price_range": "HK$10–15 per tart",
            "hours": "7:30 AM – 9:00 PM daily",
            "transport": "MTR Central Station Exit D2",
            "elderly_friendly": True,
            "tips": ["Best eaten warm — ask for freshly baked ones", "Try the egg tarts with a cup of milk tea", "The Central branch is most iconic"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Australia Dairy Company",
            "short_desc": "Legendary cha chaan teng for scrambled eggs and milk pudding.",
            "full_desc": "This 1970s-style cha chaan teng (Hong Kong-style diner) is famous for their impossibly fluffy scrambled eggs on toast and silky steamed milk pudding. The service is famously fast and no-nonsense. Expect to share tables. A quintessential Hong Kong breakfast experience.",
            "location": "Jordan, Kowloon",
            "price_range": "HK$30–60 per person",
            "hours": "7:30 AM – 11:00 PM (closed Thursdays)",
            "transport": "MTR Jordan Station Exit C2",
            "elderly_friendly": True,
            "tips": ["Decide your order before sitting — service is lightning fast", "Must try: scrambled egg toast + milk tea", "Expect shared seating"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Lei Yue Mun Seafood Village",
            "short_desc": "Pick-your-own live seafood village by the harbour. Fresh & affordable.",
            "full_desc": "Lei Yue Mun is a fishing village turned seafood haven where you can pick live seafood from market stalls and have nearby restaurants cook it for you. Enjoy the harbour views while dining on ultra-fresh fish, prawns, lobster, and crabs. A wonderful half-day outing combining market shopping and dining.",
            "location": "Lei Yue Mun, Kwun Tong, Kowloon",
            "price_range": "HK$150–400 per person",
            "hours": "11:00 AM – 10:00 PM daily",
            "transport": "MTR Yau Tong Station Exit A2, then minibus 24",
            "elderly_friendly": True,
            "tips": ["Compare prices at different stalls", "Cooking fee is separate from seafood cost", "Beautiful sunset views from the waterfront"],
            "url": "#"
        },
        # ---- SHOPPING ----
        {
            "category": "shopping",
            "name": "Ladies' Market — Tung Choi Street",
            "short_desc": "Bustling street market with bargains on clothing, accessories, souvenirs.",
            "full_desc": "Ladies' Market on Tung Choi Street stretches over a kilometre with hundreds of stalls selling affordable clothing, bags, accessories, phone cases, souvenirs, and everyday items. Despite the name, there's plenty for everyone. A lively, colourful market experience in the heart of Mong Kok.",
            "location": "Tung Choi Street, Mong Kok",
            "price_range": "HK$10–200 per item",
            "hours": "12:00 PM – 11:30 PM daily",
            "transport": "MTR Mong Kok Station Exit D3",
            "elderly_friendly": True,
            "tips": ["Bargaining is expected — start at 50% of asking price", "Best selection in the afternoon", "Watch for pickpockets in crowded areas"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Stanley Market",
            "short_desc": "Seaside market village with art, clothing, and waterfront restaurants.",
            "full_desc": "Stanley Market is a charming seaside market on the southern side of Hong Kong Island. Browse stalls selling art, silk garments, Chinese antiques, casual wear, and souvenirs. After shopping, enjoy seafood at the waterfront restaurants along Stanley Main Street. A relaxing half-day trip away from the city bustle.",
            "location": "Stanley, Hong Kong Island South",
            "price_range": "Varies widely",
            "hours": "10:00 AM – 6:00 PM daily",
            "transport": "Bus 6, 6X, 260 from Central (Exchange Square)",
            "elderly_friendly": True,
            "tips": ["Combine with a visit to Stanley Beach", "Waterfront restaurants have great views", "Less crowded on weekdays"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Jade Market — Yau Ma Tei",
            "short_desc": "Traditional jade jewellery market with hundreds of stalls of Chinese jade.",
            "full_desc": "The Jade Market in Yau Ma Tei has over 400 stalls selling jade jewellery, ornaments, and carvings. Jade holds deep cultural significance in Chinese tradition, symbolizing luck, health, and longevity. Whether you're looking for a small pendant or an elaborate jade bangle, this is the place. Adjacent to the equally fascinating Temple Street Night Market.",
            "location": "Kansu Street, Yau Ma Tei",
            "price_range": "HK$50–5,000+",
            "hours": "10:00 AM – 5:00 PM daily",
            "transport": "MTR Yau Ma Tei Station Exit C",
            "elderly_friendly": True,
            "tips": ["Bring cash for better deals", "Ask for certificates for expensive pieces", "Visit Temple Street Night Market nearby in the evening"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Sham Shui Po Fabric & Electronics",
            "short_desc": "Budget paradise for fabrics, electronics, and vintage finds.",
            "full_desc": "Sham Shui Po is Hong Kong's most authentic working-class neighbourhood. It's a treasure trove for affordable fabrics, sewing supplies, beading materials, and budget electronics. Golden Computer Arcade and nearby shops sell electronics at rock-bottom prices. The area also has some of HK's best street food.",
            "location": "Sham Shui Po, Kowloon",
            "price_range": "Very affordable",
            "hours": "10:00 AM – 8:00 PM daily",
            "transport": "MTR Sham Shui Po Station Exit D2",
            "elderly_friendly": True,
            "tips": ["Check out the fabric shops on Ki Lung Street", "Try the street food on Kweilin Street", "Golden Computer Arcade for tech bargains"],
            "url": "#"
        },
        # ---- FUN & SIGHTS ----
        {
            "category": "fun",
            "name": "Victoria Peak — The Peak",
            "short_desc": "Iconic panoramic views of the Hong Kong skyline and harbour.",
            "full_desc": "The Peak is Hong Kong's most visited attraction, offering breathtaking 360-degree views of the city skyline, Victoria Harbour, and surrounding islands. Take the historic Peak Tram (Asia's oldest funicular railway, since 1888) to the top. The Sky Terrace 428 observation deck provides the best views. The Peak also has shops, restaurants, and easy walking paths.",
            "location": "The Peak, Hong Kong Island",
            "price_range": "Peak Tram: HK$62 (seniors HK$29)",
            "hours": "Peak Tram: 7:00 AM – 12:00 AM",
            "transport": "Peak Tram from Central (Garden Road terminal) or Bus 15 from Central",
            "elderly_friendly": True,
            "tips": ["Senior discount available with HKID", "Visit at sunset for the best views", "The circular walk around the Peak is flat and easy"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Star Ferry — Victoria Harbour",
            "short_desc": "Iconic harbour crossing since 1888. One of the world's best ferry rides.",
            "full_desc": "The Star Ferry has been crossing Victoria Harbour since 1888 and is one of Hong Kong's most beloved experiences. The 10-minute ride between Central and Tsim Sha Tsui offers stunning views of both shorelines. At just a few dollars per trip, it's one of the best bargains in Hong Kong. The Tsim Sha Tsui waterfront promenade is perfect for an evening stroll.",
            "location": "Central Pier ↔ Tsim Sha Tsui Pier",
            "price_range": "HK$3.70–5.60 (seniors HK$2.20)",
            "hours": "6:30 AM – 11:30 PM daily",
            "transport": "MTR Central Station Exit A or Tsim Sha Tsui Station Exit E",
            "elderly_friendly": True,
            "tips": ["Sit on the upper deck for best views", "Senior Octopus card gets discounted fare", "Best at sunset or for the Symphony of Lights at 8 PM"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Nan Lian Garden & Chi Lin Nunnery",
            "short_desc": "Tranquil Tang dynasty-style garden with bonsai, ponds, and a golden pagoda.",
            "full_desc": "Nan Lian Garden is a beautifully maintained Tang dynasty-style garden in the heart of urban Kowloon. Connected to the elegant Chi Lin Nunnery, the garden features manicured bonsai, lotus ponds, waterfalls, rocky hills, and the stunning golden Pavilion of Absolute Perfection. A serene escape from the city. Free entry.",
            "location": "Diamond Hill, Kowloon",
            "price_range": "Free entry",
            "hours": "7:00 AM – 9:00 PM daily",
            "transport": "MTR Diamond Hill Station Exit C2",
            "elderly_friendly": True,
            "tips": ["Completely free — one of HK's best free attractions", "Flat, wheelchair-accessible paths throughout", "Try the vegetarian restaurant inside Chi Lin Nunnery"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Hong Kong Wetland Park",
            "short_desc": "Nature reserve with bird-watching, butterfly gardens, and mangroves.",
            "full_desc": "Hong Kong Wetland Park is a 61-hectare nature reserve in Tin Shui Wai featuring indoor galleries, outdoor wetland habitats, bird hides, a butterfly garden, and mangrove boardwalks. Watch for the park's resident crocodile 'Pui Pui'. Educational and relaxing, it's a wonderful day out for nature lovers of all ages.",
            "location": "Tin Shui Wai, New Territories",
            "price_range": "HK$30 (seniors HK$15)",
            "hours": "10:00 AM – 5:00 PM (closed Tuesdays)",
            "transport": "MTR Wetland Park Station, 5 min walk",
            "elderly_friendly": True,
            "tips": ["Bring binoculars for bird-watching", "Flat boardwalks suitable for wheelchairs", "Best visited in autumn for migratory birds"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Temple Street Night Market",
            "short_desc": "Atmospheric night market with food stalls, fortune tellers, and street opera.",
            "full_desc": "Temple Street Night Market comes alive after dark with hundreds of street stalls, open-air food vendors (try the clay pot rice and typhoon shelter crab), fortune tellers, and sometimes traditional Cantonese street opera. It's a vibrant window into old Hong Kong culture. The market is named after the Tin Hau Temple at its centre.",
            "location": "Temple Street, Yau Ma Tei & Jordan",
            "price_range": "HK$50–200 per person (food & shopping)",
            "hours": "4:00 PM – 12:00 AM daily (best after 7 PM)",
            "transport": "MTR Jordan Station Exit A or Yau Ma Tei Station Exit C",
            "elderly_friendly": True,
            "tips": ["Best atmosphere after 7 PM when fully open", "Try the dai pai dong street food near Temple Street", "Visit Tin Hau Temple for a cultural experience"],
            "url": "#"
        },
        # ---- EVENTS ----
        {
            "category": "events",
            "name": "Chinese New Year Celebrations 2026",
            "short_desc": "Fireworks, night parade, flower markets across Hong Kong.",
            "full_desc": "Chinese New Year 2026 (Year of the Horse) falls on 17 February. Key events include the spectacular fireworks display over Victoria Harbour, the international night parade in Tsim Sha Tsui, and traditional flower markets (年宵市場) across all districts. Victoria Park hosts the largest flower market. Temples are busy with worshippers on New Year's Day.",
            "location": "Citywide — Victoria Harbour, Tsim Sha Tsui, Victoria Park",
            "price_range": "Mostly free",
            "hours": "Various dates around 17 Feb 2026",
            "transport": "MTR to respective locations",
            "elderly_friendly": True,
            "tips": ["Flower markets start about a week before New Year", "Victoria Harbour fireworks best viewed from Tsim Sha Tsui waterfront", "Wear red for good luck!"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Cheung Chau Bun Festival 2026",
            "short_desc": "Unique annual festival with bun-snatching competition and Piu Sik parades.",
            "full_desc": "The Cheung Chau Bun Festival (太平清醮) is a unique annual Taoist festival held on the tiny island of Cheung Chau. Highlights include the famous bun-snatching competition where participants climb 14-metre bun towers, and the colourful Piu Sik (飄色) parade with children suspended in the air wearing elaborate costumes. A truly unique Hong Kong cultural experience.",
            "location": "Cheung Chau Island",
            "price_range": "Free (ferry ticket required)",
            "hours": "May 2026 (dates vary by lunar calendar)",
            "transport": "Ferry from Central Pier 5 to Cheung Chau (35-55 min)",
            "elderly_friendly": True,
            "tips": ["Arrive early — ferries get very crowded", "The island is small & walkable", "Try the festival buns (平安包) sold everywhere"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Mid-Autumn Festival Lantern Displays",
            "short_desc": "Spectacular lantern displays in Victoria Park and across HK districts.",
            "full_desc": "The Mid-Autumn Festival features stunning traditional and modern lantern displays across Hong Kong. Victoria Park hosts the largest display with themed lanterns, live performances, and traditional games. Many districts set up their own displays at local parks. People carry lanterns, eat mooncakes, and enjoy the full moon together. A wonderful family-friendly festival.",
            "location": "Victoria Park, Tai Hang (Fire Dragon), various districts",
            "price_range": "Free",
            "hours": "September 2026 (15th day of 8th lunar month)",
            "transport": "MTR Tin Hau Station for Victoria Park",
            "elderly_friendly": True,
            "tips": ["Don't miss the Tai Hang Fire Dragon Dance — a three-night tradition", "Try different mooncake flavours at local bakeries", "Bring a lantern to join the celebrations"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Hong Kong Hiking Festival (Autumn)",
            "short_desc": "Organized senior-friendly hikes with guides on scenic HK trails.",
            "full_desc": "Autumn in Hong Kong (October–December) is the best hiking season with cool, dry weather. Many organizations host guided group hikes suitable for seniors, including easy routes along the Dragon's Back, Lamma Island Family Trail, and Tai Tam Reservoir path. These organized events often include transport, lunch, and experienced guides. A great way to socialize and stay active.",
            "location": "Various trails across Hong Kong",
            "price_range": "Free to HK$100 (organized events)",
            "hours": "October – December 2026",
            "transport": "Varies by trail",
            "elderly_friendly": True,
            "tips": ["Dragon's Back and Lamma Family Trail are easiest", "Bring water and wear comfortable shoes", "Check LCSD or hiking groups for organized senior events"],
            "url": "#"
        },
    ],
    "zh-HK": [
        # ---- 美食 ----
        {
            "category": "food",
            "name": "添好運 — 點心",
            "short_desc": "全球最平米芝蓮一星餐廳。招牌酥皮焗叉燒包好出名。",
            "full_desc": "添好運係全球最平嘅米芝蓮一星餐廳，招牌酥皮焗叉燒包外層酥脆帶甜，內餡叉燒鬆軟惹味。點心款式豐富，全部即點即蒸，新鮮熱辣。價錢親民，幾十蚊已經食到飽。分店遍布全港各區。",
            "location": "深水埗、旺角、中環（多間分店）",
            "price_range": "每位 HK$50–150",
            "hours": "每日 10:00 – 21:30",
            "transport": "港鐵深水埗站 B2 出口（原店）",
            "elderly_friendly": True,
            "tips": ["早啲去排隊會快好多", "一定要試招牌酥皮焗叉燒包", "大部分分店都有升降機"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "麥奀記 — 雲吞麵",
            "short_desc": "傳奇雲吞麵，1920年代至今。幼細彈牙竹昇麵配鮮蝦雲吞。",
            "full_desc": "麥奀記有近百年歷史，係香港最出名嘅雲吞麵之一。手打竹昇麵幼細彈牙，配上鮮甜蝦湯底同埋飽滿嘅鮮蝦雲吞。簡單、實惠、好食。每碗都係對傳統嘅堅持。",
            "location": "中環威靈頓街",
            "price_range": "每位 HK$40–80",
            "hours": "每日 11:00 – 20:00",
            "transport": "港鐵中環站 D2 出口，步行5分鐘",
            "elderly_friendly": True,
            "tips": ["份量唔大，啱晒一次試幾款", "部分分店淨收現金", "有冷氣座位"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "泰昌餅家 — 蛋撻",
            "short_desc": "全港最出名嘅蛋撻。酥皮鬆化，蛋漿嫩滑香甜。",
            "full_desc": "泰昌餅家自1954年開業，蛋撻係佢嘅招牌。末代港督彭定康都係佢嘅忠實粉絲，所以又叫做「肥彭蛋撻」。酥皮層層鬆化，蛋漿嫩滑帶甜，每一啖都充滿港式風味。必試之選。",
            "location": "中環擺花街（原店）；多間分店",
            "price_range": "每個蛋撻 HK$10–15",
            "hours": "每日 7:30 – 21:00",
            "transport": "港鐵中環站 D2 出口",
            "elderly_friendly": True,
            "tips": ["趁熱食最好味 — 可以問佢攞新鮮出爐嘅", "蛋撻配奶茶係絕配", "中環原店最有懷舊味"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "澳洲牛奶公司",
            "short_desc": "傳奇茶餐廳，炒蛋多士同燉奶極受歡迎。",
            "full_desc": "呢間70年代風格嘅茶餐廳以超滑炒蛋多士同蒸燉奶聞名。服務員出名快手快腳，坐低就要即叫。可能要同人搭枱。係最正宗嘅香港早餐體驗。",
            "location": "佐敦，九龍",
            "price_range": "每位 HK$30–60",
            "hours": "7:30 – 23:00（逢星期四休息）",
            "transport": "港鐵佐敦站 C2 出口",
            "elderly_friendly": True,
            "tips": ["坐低之前諗定叫咩 — 服務好快㗎", "必試：炒蛋多士 + 奶茶", "預咗要搭枱"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "鯉魚門海鮮街",
            "short_desc": "自己揀活海鮮，對住海景食新鮮即煮海鮮。",
            "full_desc": "鯉魚門係一個漁村變成嘅海鮮天堂，可以喺海鮮檔揀活海鮮，然後拎到旁邊嘅食肆代煮。對住海港景色食新鮮魚、蝦、龍蝦、蟹，好寫意。係一個好適合半日遊嘅好去處。",
            "location": "鯉魚門，觀塘，九龍",
            "price_range": "每位 HK$150–400",
            "hours": "每日 11:00 – 22:00",
            "transport": "港鐵油塘站 A2 出口，轉小巴24",
            "elderly_friendly": True,
            "tips": ["多行幾檔比較價錢", "加工費同海鮮價錢係分開計", "黃昏景色特別靚"],
            "url": "#"
        },
        # ---- 購物 ----
        {
            "category": "shopping",
            "name": "女人街 — 通菜街",
            "short_desc": "旺角人氣露天市場，衫褲鞋襪飾物樣樣平。",
            "full_desc": "女人街喺通菜街，成個市場成成一公里長，有幾百個攤檔賣平價衫褲、手袋、飾物、手機殼、紀念品同日用品。雖然叫女人街，但係男女老幼都啱去。旺角最熱鬧嘅市集體驗。",
            "location": "旺角通菜街",
            "price_range": "每件 HK$10–200",
            "hours": "每日 12:00 – 23:30",
            "transport": "港鐵旺角站 D3 出口",
            "elderly_friendly": True,
            "tips": ["講價係常識，可以由一半開始還", "下晝先至最多嘢揀", "人多注意銀包財物"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "赤柱市場",
            "short_desc": "海邊市集，有藝術品、衫褲同海景餐廳。",
            "full_desc": "赤柱市場係港島南區嘅海邊市集，可以買到藝術品、絲綢衫、中式古董、休閒服同紀念品。行完街可以去海邊食海鮮，環境優美。離開市區半日遊好選擇。",
            "location": "赤柱，港島南",
            "price_range": "價錢唔一",
            "hours": "每日 10:00 – 18:00",
            "transport": "中環（交易廣場）搭巴士 6、6X、260",
            "elderly_friendly": True,
            "tips": ["順便去赤柱沙灘行吓", "海邊餐廳景色一流", "平日去人少好多"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "玉器市場 — 油麻地",
            "short_desc": "傳統玉器市場，有幾百個攤檔賣各式中國玉器。",
            "full_desc": "油麻地玉器市場有超過400個攤檔，賣玉器首飾、擺設同玉雕。玉器喺中國文化裏面代表好運、健康同長壽。無論係小吊墜定精緻玉鐲，呢度應有盡有。旁邊仲有廟街夜市。",
            "location": "油麻地甘肅街",
            "price_range": "HK$50–5,000+",
            "hours": "每日 10:00 – 17:00",
            "transport": "港鐵油麻地站 C 出口",
            "elderly_friendly": True,
            "tips": ["帶現金會有更好價錢", "貴嘅玉器記得要求證書", "晚上順便行廟街夜市"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "深水埗布藝及電子商場",
            "short_desc": "平價天堂，布藝、電子產品同懷舊雜貨。",
            "full_desc": "深水埗係香港最地道嘅草根社區，平價布藝、製衣材料、珠仔材料同電子產品應有盡有。黃金電腦商場有最平嘅電子產品。呢區仲有好多好味街頭小食。",
            "location": "深水埗，九龍",
            "price_range": "非常平",
            "hours": "每日 10:00 – 20:00",
            "transport": "港鐵深水埗站 D2 出口",
            "elderly_friendly": True,
            "tips": ["基隆街一帶有最多布藝舖", "桂林街有好多街頭小食", "黃金電腦商場買電子嘢最平"],
            "url": "#"
        },
        # ---- 玩樂 ----
        {
            "category": "fun",
            "name": "太平山頂",
            "short_desc": "香港最著名嘅觀景點，可以睇到成個維港同城市景色。",
            "full_desc": "太平山頂係香港最受歡迎嘅景點，可以360度睇到城市天際線、維多利亞港同周圍嘅島嶼。搭歷史悠久嘅山頂纜車（亞洲最古老嘅纜索鐵路，1888年至今）上去。凌霄閣觀景台428係最佳觀景位置。山頂仲有商店、餐廳同易行嘅步行徑。",
            "location": "太平山，港島",
            "price_range": "山頂纜車：HK$62（長者 HK$29）",
            "hours": "山頂纜車：7:00 – 00:00",
            "transport": "中環花園道搭山頂纜車或中環搭巴士15號",
            "elderly_friendly": True,
            "tips": ["長者持香港身份證有優惠", "日落時分去景色最靚", "環山步行徑平坦易行"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "天星小輪 — 維多利亞港",
            "short_desc": "1888年至今嘅經典渡輪，世界最佳渡輪體驗之一。",
            "full_desc": "天星小輪自1888年穿梭維港，係香港最受歡迎嘅體驗之一。10分鐘嘅船程由中環去到尖沙咀，兩岸景色盡收眼底。幾蚊雞就搭到，性價比極高。尖沙咀海濱長廊好適合傍晚散步。",
            "location": "中環碼頭 ↔ 尖沙咀碼頭",
            "price_range": "HK$3.70–5.60（長者 HK$2.20）",
            "hours": "每日 6:30 – 23:30",
            "transport": "港鐵中環站 A 出口或尖沙咀站 E 出口",
            "elderly_friendly": True,
            "tips": ["坐上層景色最好", "長者八達通有優惠", "日落或晚上8點幻彩詠香江最靚"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "南蓮園池 & 志蓮淨苑",
            "short_desc": "寧靜唐式園林，有盆景、荷花池同金色涼亭。",
            "full_desc": "南蓮園池係一個保養得好靚嘅唐朝風格園林，位於城市中心嘅鑽石山。連住典雅嘅志蓮淨苑，園內有精心修剪嘅盆景、荷花池、瀑布、假山同華麗嘅金色圓滿閣。城市中嘅寧靜角落。免費入場。",
            "location": "鑽石山，九龍",
            "price_range": "免費入場",
            "hours": "每日 7:00 – 21:00",
            "transport": "港鐵鑽石山站 C2 出口",
            "elderly_friendly": True,
            "tips": ["完全免費，係香港最佳免費景點之一", "全園平坦，輪椅都行到", "可以試吓志蓮淨苑入面嘅素食餐廳"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "香港濕地公園",
            "short_desc": "自然保護區，有觀鳥、蝴蝶園同紅樹林木板步道。",
            "full_desc": "香港濕地公園位於天水圍，佔地61公頃，有室內展覽館、戶外濕地生態、觀鳥屋、蝴蝶園同紅樹林步道。仲可以睇到公園嘅明星鱷魚「貝貝」。既有教育意義又輕鬆寫意，適合各年齡層嘅自然愛好者。",
            "location": "天水圍，新界",
            "price_range": "HK$30（長者 HK$15）",
            "hours": "10:00 – 17:00（逢星期二休園）",
            "transport": "港鐵濕地公園站，步行5分鐘",
            "elderly_friendly": True,
            "tips": ["帶望遠鏡觀鳥更有趣", "木板步道平坦，輪椅都行到", "秋天嚟最好，可以睇到候鳥"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "廟街夜市",
            "short_desc": "有氣氛嘅夜市，有街頭小食、占卜同粵劇。",
            "full_desc": "廟街夜市天黑後最熱鬧，有幾百個街邊攤檔、露天大牌檔（試吓煲仔飯同避風塘炒蟹）、占卜攤同偶爾嘅粵劇表演。係睇舊香港文化嘅好地方。夜市以中間嘅天后廟命名。",
            "location": "廟街，油麻地及佐敦",
            "price_range": "每位 HK$50–200（食嘢同購物）",
            "hours": "每日 16:00 – 00:00（19:00後最旺）",
            "transport": "港鐵佐敦站 A 出口或油麻地站 C 出口",
            "elderly_friendly": True,
            "tips": ["晚上7點後最有氣氛", "試吓廟街附近嘅大牌檔小食", "去天后廟參拜感受文化"],
            "url": "#"
        },
        # ---- 活動 ----
        {
            "category": "events",
            "name": "2026 農曆新年慶祝活動",
            "short_desc": "維港煙花、花車巡遊、年宵花市遍布全港。",
            "full_desc": "2026年農曆新年（馬年）喺2月17日。重點活動包括維港上空嘅壯觀煙花匯演、尖沙咀國際花車巡遊、同遍布全港嘅年宵花市。維園有最大嘅花市。年初一各大廟宇會好多人拜神。",
            "location": "全港 — 維港、尖沙咀、維園",
            "price_range": "大部分免費",
            "hours": "2026年2月17日前後",
            "transport": "港鐵到相關地點",
            "elderly_friendly": True,
            "tips": ["年宵花市喺新年前一個禮拜開始", "維港煙花喺尖沙咀海邊睇最靚", "著紅色衫代表好運！"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "2026 長洲太平清醮",
            "short_desc": "獨特年度節慶，有搶包山比賽同飄色巡遊。",
            "full_desc": "長洲太平清醮係一個好特別嘅年度道教節日，喺長洲島舉行。重點包括出名嘅搶包山比賽（參加者要爬上14米高嘅包山）同色彩繽紛嘅飄色巡遊（小朋友著住靚衫凌空飛起）。真係獨一無二嘅香港文化體驗。",
            "location": "長洲島",
            "price_range": "免費（需要買船票）",
            "hours": "2026年5月（日期按農曆定）",
            "transport": "中環5號碼頭搭渡輪去長洲（35-55分鐘）",
            "elderly_friendly": True,
            "tips": ["早啲去碼頭，船會好迫", "島仔唔大，行路就得", "記得買「平安包」食"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "中秋節花燈會",
            "short_desc": "維園同各區公園嘅大型花燈展覽。",
            "full_desc": "中秋節有壯觀嘅傳統同現代花燈展覽遍布全港。維園有最大型嘅花燈會，有主題花燈、現場表演同傳統遊戲。好多區都會喺當地公園搞花燈展。市民會提燈籠、食月餅、賞月。好適合一家大細嘅節日。",
            "location": "維園、大坑（舞火龍）、各區",
            "price_range": "免費",
            "hours": "2026年9月（農曆八月十五）",
            "transport": "港鐵天后站去維園",
            "elderly_friendly": True,
            "tips": ["一定唔好錯過大坑舞火龍 — 一連三晚嘅傳統", "試吓唔同口味嘅月餅", "帶個燈籠一齊玩"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "秋季香港行山節",
            "short_desc": "有導賞嘅長者友善行山團，行香港靚景山徑。",
            "full_desc": "香港秋天（10至12月）係最佳行山季節，天氣涼爽乾燥。好多機構會搞適合長者嘅導賞行山團，包括輕鬆路線如龍脊、南丫島家樂徑同大潭水塘路。有啲活動包交通、午餐同經驗豐富嘅導遊。係保持活躍同社交嘅好方法。",
            "location": "全港各行山徑",
            "price_range": "免費至 HK$100（有組織活動）",
            "hours": "2026年10月至12月",
            "transport": "視乎路線而定",
            "elderly_friendly": True,
            "tips": ["龍脊同南丫島家樂徑最輕鬆", "記得帶水同著舒服嘅鞋", "留意康文署或行山群組嘅長者活動"],
            "url": "#"
        },
    ]
}


def get_hk_guide_data(lang: str = 'en') -> list[dict]:
    """Return curated HK local guide data for the given language."""
    return HK_GUIDE_DATA.get(lang, HK_GUIDE_DATA["en"])


@app.get("/hk_guide", response_class=HTMLResponse)
async def hk_guide_page(request: Request):
    """Render the HK Local Guide page."""
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("hk_guide.html", tpl_context(request))


@app.get("/get_hk_guide")
async def get_hk_guide(request: Request, refresh: int = 0):
    """Return HK local guide data as JSON (cached 30 min)."""
    import time as _time
    lang = get_lang(request)
    now = _time.time()

    # Use cache unless forced refresh
    if (not refresh
            and _hk_guide_cache["data"]
            and (now - _hk_guide_cache["timestamp"]) < 1800
            and _hk_guide_cache["lang"] == lang):
        return JSONResponse(_hk_guide_cache["data"])

    items = get_hk_guide_data(lang)
    ts_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    result = {
        "items": items,
        "last_updated": ts_str,
        "total": len(items),
    }
    _hk_guide_cache["data"] = result
    _hk_guide_cache["timestamp"] = now
    _hk_guide_cache["lang"] = lang
    return JSONResponse(result)

# ---------------------------------------------------------------------------
# Development server entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    import builtins as _builtins
    # Restore original print for the concise startup message (if it exists)
    try:
        _builtins.print = _builtins._original_print
    except Exception:
        pass

    port = int(os.environ.get("PORT", 5000))
    url = f"http://localhost:{port}"
    print(f"Server running: {url}")

    # Run Uvicorn with quieter logging. Access logs and INFO-level logs are
    # disabled to keep console output minimal.
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", access_log=False)