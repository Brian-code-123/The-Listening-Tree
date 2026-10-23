"""Endpoints called by the platform, not by users.

Vercel does not run the background loop in `app/background.py` (serverless
functions cannot), so the retention jobs run from a Vercel cron that calls
this route daily. Vercel sends `Authorization: Bearer $CRON_SECRET`.
"""
import hmac
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import background

router = APIRouter()


def _authorised(request: Request) -> bool:
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        return False  # not configured: refuse everyone rather than allow everyone
    supplied = request.headers.get("authorization", "")
    return hmac.compare_digest(supplied.encode(), f"Bearer {secret}".encode())


@router.get("/internal/cron/cleanup")
async def cleanup(request: Request):
    if not _authorised(request):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    deleted = {
        "verifications": await background.purge_expired_verifications(),
        "soft_deleted": await background.purge_soft_deleted(),
        "security_events": await background.purge_old_security_events(),
    }
    await background.cleanup_old_conversations()
    await background.cleanup_old_chat_history()
    await background.cleanup_old_rate_limit_events()
    await background.auto_expire_old_reminders()
    return {"ok": True, "deleted": deleted}
