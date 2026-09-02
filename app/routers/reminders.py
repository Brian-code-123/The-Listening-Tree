"""Reminder management endpoints.

Reminder creation/deletion historically only happened via free-text
commands inside `/get_response` (see app/routers/chat.py) — POST
/reminders and DELETE /reminders/{id} below are real REST endpoints added
for the Next.js /chat port, sharing their DB logic with the NL-command
path via app/services/reminders.py rather than duplicating it.
"""
import re
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from app.core.session import get_user
from app.db import queries as db
from app.services.reminders import (
    create_reminder,
    delete_reminder_by_id,
    delete_reminder_by_label,
)

router = APIRouter()

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


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
        "SELECT id, label, reminder_time, is_active FROM reminders WHERE user_id = ? AND DATE(created_at) = ? ORDER BY created_at DESC",
        (uid, today),
    )
    reminders = [
        {"id": r["id"], "label": r["label"], "time": r["reminder_time"], "active": bool(r["is_active"])}
        for r in c.fetchall()
    ]
    await conn.close()
    return JSONResponse({"reminders": reminders})


@router.post("/reminders")
async def create_reminder_endpoint(request: Request, label: str = Form(...), time: str = Form(...)):
    """REST create — the Next.js /chat port's reminder panel uses this
    instead of synthesizing a "set reminder ..." chat command."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    label = label.strip()
    if not label:
        return JSONResponse({"success": False, "message": "Label is required"}, status_code=400)
    if not _TIME_RE.match(time):
        return JSONResponse({"success": False, "message": "Time must be HH:MM (24-hour)"}, status_code=400)
    new_id = await create_reminder(uid, label, time)
    return JSONResponse({"success": True, "id": new_id, "label": label, "time": time})


@router.delete("/reminders/{reminder_id}")
async def delete_reminder_endpoint(request: Request, reminder_id: int):
    """REST delete, keyed on id — not label, since labels aren't unique
    and a by-label delete would be ambiguous when duplicates exist."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    found = await delete_reminder_by_id(uid, reminder_id)
    if not found:
        return JSONResponse({"success": False, "message": "Reminder not found"}, status_code=404)
    return JSONResponse({"success": True})
