"""Shared reminder create/delete logic.

Used by both the natural-language command path (typing "set reminder ..."
into chat, parsed in app/routers/chat.py) and the REST endpoints
(app/routers/reminders.py, added for the Next.js /chat port) — one
implementation instead of duplicating the insert/delete SQL in two places.
"""
from datetime import datetime

from app.db import queries as db


async def create_reminder(uid: int, label: str, reminder_time: str) -> int:
    """Insert a new active reminder for *uid* and return its id.

    Caller is responsible for validating `reminder_time` is HH:MM in a
    valid 24-hour range — this function does not re-validate it.
    """
    conn = await db.get_db()
    c = conn.cursor()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db.db_execute(
        c,
        "INSERT INTO reminders (user_id, label, reminder_time, is_active, created_at) VALUES (?, ?, ?, TRUE, ?) RETURNING id",
        (uid, label, reminder_time, ts),
    )
    new_id = c.fetchone()["id"]
    await conn.commit()
    await conn.close()
    return new_id


async def delete_reminder_by_label(uid: int, label: str) -> bool:
    """Delete a reminder by label (the NL-command path — labels aren't
    guaranteed unique, so this deletes at most the matching row(s) for
    this user; kept as-is to preserve existing chat-command behavior)."""
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "DELETE FROM reminders WHERE user_id = ? AND label = ?", (uid, label))
    found = db._safe_rowcount(c) > 0
    await conn.commit()
    await conn.close()
    return found


async def delete_reminder_by_id(uid: int, reminder_id: int) -> bool:
    """Delete a reminder by id (the REST path) — unambiguous even when
    multiple reminders share a label, unlike delete_reminder_by_label."""
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "DELETE FROM reminders WHERE user_id = ? AND id = ?", (uid, reminder_id))
    found = db._safe_rowcount(c) > 0
    await conn.commit()
    await conn.close()
    return found
