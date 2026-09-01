"""Health checks — a bare public probe and a verbose authenticated one."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.session import get_user
from app.db import pool as db_pool
from app.db import queries as db
from app.db import schema

router = APIRouter()


@router.get("/health/db")
async def health_db(request: Request):
    """Database connectivity health check: verify PostgreSQL is accessible.

    Returns a bare {"ok": bool} to unauthenticated callers — infra details
    (hostname, raw exception text) are only included for a logged-in caller,
    since this is a public repo/deployment and that's reconnaissance-useful
    info to hand an anonymous caller for free.
    """
    uid = get_user(request)
    initialized = await schema.ensure_db_initialized(strict=False)
    conn = None
    try:
        conn = await db.get_db()
        c = conn.cursor()
        await c.execute("SELECT 1")
        _ = c.fetchone()
        body = {"ok": True}
        if uid is not None:
            body.update({
                "backend": db_pool.RUNTIME_DB_BACKEND,
                "configured_backend": db_pool.DB_BACKEND,
                "db_initialized": initialized,
                "db_init_error": schema.get_init_error(),
                "db_url_source": db_pool.DB_URL_SOURCE,
                "db_runtime_label": db_pool.DB_RUNTIME_LABEL,
                "db_hostname": db_pool.DB_HOSTNAME,
                "db_hostaddr": db_pool.DB_HOSTADDR,
                "db_last_pg_attempts": db_pool.LAST_PG_ATTEMPTS,
            })
        return JSONResponse(body)
    except Exception as e:
        body = {"ok": False}
        if uid is not None:
            body.update({
                "backend": db_pool.RUNTIME_DB_BACKEND,
                "configured_backend": db_pool.DB_BACKEND,
                "db_initialized": initialized,
                "db_init_error": schema.get_init_error(),
                "db_url_source": db_pool.DB_URL_SOURCE,
                "db_runtime_label": db_pool.DB_RUNTIME_LABEL,
                "db_hostname": db_pool.DB_HOSTNAME,
                "db_hostaddr": db_pool.DB_HOSTADDR,
                "db_last_pg_attempts": db_pool.LAST_PG_ATTEMPTS,
                "error": str(e),
            })
        return JSONResponse(body, status_code=500)
    finally:
        if conn is not None:
            await conn.close()


@router.get("/health")
async def health():
    """Basic process-level health probe for uptime checks — deliberately
    minimal (no infra details) since this endpoint is public/unauthenticated
    by design. Use /health/db while logged in for the verbose diagnostic."""
    return JSONResponse({"ok": True, "service": "the-listening-tree"})
