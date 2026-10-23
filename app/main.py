"""FastAPI application factory: middleware, static mount, routers, lifespan.

This is the single source of truth for the ASGI `app` object — both
`run.py` (local dev server) and `api/index.py` (Vercel entrypoint) just
import `app` from here.
"""
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.background import run_periodic_tasks
from app.core import config
from app.core.session import RememberMeCookieMiddleware
from app.core.session_guard import SessionRevocationMiddleware
from app.core.templates import BASE_DIR, CachedStaticFiles
from app.db import pool as db_pool
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.security_headers import SECURITY_HEADERS, SecurityHeadersMiddleware, cors_origins
from app.core.session import get_lang
from app.db import schema
from app.services.rate_limit import RateLimitUnavailable
from app.routers import account, auth, chat, conversations, health, hk_guide, internal, pages, reminders

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_pool.create_pool()

    # Initialize database schema on app startup (not at import time).
    # This prevents import-time failures in serverless handlers.
    try:
        await schema.ensure_db_initialized(strict=not config.IN_PRODUCTION)
    except Exception as e:
        logger.error(f"[DB] Startup initialization failed: {e}")
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

    await db_pool.close_pool()


# ---------------------------------------------------------------------------
# Application initialisation
# ---------------------------------------------------------------------------
# The interactive docs and the OpenAPI schema list every route; in production
# that is a free map of the attack surface, so they exist only locally.
app = FastAPI(
    title="The Listening Tree",
    description="Bilingual AI companion chatbot for elderly wellness",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if config.IN_PRODUCTION else "/docs",
    redoc_url=None if config.IN_PRODUCTION else "/redoc",
    openapi_url=None if config.IN_PRODUCTION else "/openapi.json",
)


@app.exception_handler(Exception)
async def _unhandled_error(request: Request, exc: Exception):
    """Whatever went wrong, the caller gets a fixed message and an id to quote;
    the exception text (which can carry SQL values or an email address) stays out
    of the response and out of the log."""
    request_id = request.headers.get("x-vercel-id") or uuid.uuid4().hex
    logger.error("Unhandled %s on %s %s [%s]", type(exc).__name__, request.method, request.url.path, request_id)
    return JSONResponse({"detail": "Internal error", "request_id": request_id}, status_code=500, headers=SECURITY_HEADERS)



@app.exception_handler(RateLimitUnavailable)
async def _rate_limiter_down(request: Request, exc: RateLimitUnavailable):
    """The limiter fails closed: no counter means no safe way to let a request
    through, but the caller gets a plain "try again" instead of a stack trace."""
    message = "Service is busy. Please try again in a moment." if get_lang(request) == "en" else "服務繁忙，請稍後再試"
    return JSONResponse({"success": False, "message": message, "error": message, "text": ""}, status_code=503)


# The app is currently only ever called same-origin (Jinja-rendered pages'
# own AJAX calls, and the Capacitor mobile build's WebView navigates
# directly to the deployed URL via `server.url` in capacitor.config.ts,
# rather than serving templates locally and calling out) — so this is
# defense-in-depth against a *future* cross-origin caller, not a fix for
# anything currently broken. An explicit allowlist, not a wildcard, since
# `allow_credentials=True` is required for the session cookie to work and
# browsers refuse to combine that with `allow_origins=["*"]` anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(config.IN_PRODUCTION),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Accept-Language"],
)

# Added before SessionMiddleware so it sits *inside* it and can read the session.
app.add_middleware(SessionRevocationMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    session_cookie="lt_session",
    max_age=config.REMEMBER_ME_MAX_AGE,
    same_site="lax",
    https_only=config.IN_PRODUCTION,
)
# Added after SessionMiddleware so it sits *outside* it: SessionMiddleware
# writes the Set-Cookie header first, then this one gets to rewrite it.
app.add_middleware(RememberMeCookieMiddleware)
# Inside the security headers (so a 413 carries them) but outside the session, so
# an oversized body is refused before anything is parsed or looked up.
app.add_middleware(BodySizeLimitMiddleware)
# Outermost, so every response (including redirects and CORS replies) gets the headers.
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(chat.router)
app.include_router(reminders.router)
app.include_router(conversations.router)
app.include_router(hk_guide.router)
app.include_router(health.router)
app.include_router(internal.router)
