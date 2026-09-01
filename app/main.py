"""FastAPI application factory: middleware, static mount, routers, lifespan.

This is the single source of truth for the ASGI `app` object — both
`run.py` (local dev server) and `api/index.py` (Vercel entrypoint) just
import `app` from here.
"""
import asyncio
import builtins as _builtins
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.background import run_periodic_tasks
from app.core import config
from app.core.session import RememberMeCookieMiddleware
from app.core.templates import BASE_DIR, CachedStaticFiles
from app.db import pool as db_pool
from app.db import schema
from app.routers import auth, chat, conversations, health, hk_guide, pages, reminders


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_pool.create_pool()

    # Initialize database schema on app startup (not at import time).
    # This prevents import-time failures in serverless handlers.
    try:
        await schema.ensure_db_initialized(strict=not config.IN_PRODUCTION)
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

    await db_pool.close_pool()


# ---------------------------------------------------------------------------
# Application initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="The Listening Tree",
    description="Bilingual AI companion chatbot for elderly wellness",
    version="2.0.0",
    lifespan=lifespan
)

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
    allow_origins=[
        "https://the-listening-tree.vercel.app",
        "capacitor://localhost",
        "http://localhost",
        "http://localhost:5000",
        "http://localhost:5001",
        # web-next/ — local-only Next.js proof of concept (see
        # docs/FRONTEND_ROADMAP.md), never deployed. Safe to add since
        # allow_origins is an explicit allowlist, not a wildcard.
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(reminders.router)
app.include_router(conversations.router)
app.include_router(hk_guide.router)
app.include_router(health.router)
