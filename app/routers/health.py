"""Health checks. Both answer with almost nothing: this is a public deployment,
and a hostname, driver detail or exception text is reconnaissance handed to
whoever asks (even a self-registered account). Details go to the server log."""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import queries as db
from app.db import schema

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health/db")
async def health_db():
    """Database connectivity check: is PostgreSQL reachable?"""
    conn = None
    try:
        await schema.ensure_db_initialized(strict=False)
        conn = await db.get_db()
        c = conn.cursor()
        await c.execute("SELECT 1")
        c.fetchone()
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.warning("Database health check failed (%s)", type(e).__name__)
        return JSONResponse({"ok": False}, status_code=500)
    finally:
        if conn is not None:
            await conn.close()


@router.get("/health")
async def health():
    """Basic process-level health probe for uptime checks, deliberately minimal
    (no infra details) because it is public by design."""
    return JSONResponse({"ok": True, "service": "the-listening-tree"})
