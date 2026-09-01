"""Reminder management endpoints (AJAX) — deactivate + list.

Reminder creation/deletion happen via free-text commands inside
`/get_response` (see app/routers/chat.py), not here.
"""
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from app.core.session import get_user
from app.db import queries as db

router = APIRouter()


@router.post("/deactivate_reminder")
async def deactivate_reminder(request: Request, label: str = Form(...)):
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False}, status_code=401)
    conn = await db.get_db()
    c = conn.cursor()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db.db_execute(c, "UPDATE reminders SET is_active = FALSE, updated_at = ? WHERE user_id = ? AND label = ?", (ts, uid, label))
    await conn.commit()
    await conn.close()
    return JSONResponse({"success": True})


@router.get("/get_reminders")
async def get_reminders(request: Request):
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"reminders": []})
    conn = await db.get_db()
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    await db.db_execute(
        c,
        "SELECT label, reminder_time, is_active FROM reminders WHERE user_id = ? AND DATE(created_at) = ? ORDER BY created_at DESC",
        (uid, today),
    )
    reminders = [{"label": r["label"], "time": r["reminder_time"], "active": bool(r["is_active"])} for r in c.fetchall()]
    await conn.close()
    return JSONResponse({"reminders": reminders})
