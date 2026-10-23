"""Shared reminder create/delete logic.

Used by both the natural-language command path (typing "set reminder ..."
into chat, parsed in app/routers/chat.py) and the REST endpoints
(app/routers/reminders.py, added for the Next.js /chat port) — one
implementation instead of duplicating the insert/delete SQL in two places.
"""
from datetime import datetime

from app.db import queries as db

MAX_ACTIVE_REMINDERS = 50
MAX_REMINDER_LABEL = 100


class ReminderLimitReached(Exception):
    """The user already has MAX_ACTIVE_REMINDERS active reminders."""


class ReminderLabelTooLong(ValueError):
    """The label is longer than MAX_REMINDER_LABEL."""


async def create_reminder(uid: int, label: str, reminder_time: str, repeat_type: str = "once") -> int:
    """Insert a new active reminder for *uid* and return its id.

    `repeat_type` is "once" (default) or "daily"; daily reminders survive
    past the day they were created and are not deleted after firing.

    Caller is responsible for validating `reminder_time` is HH:MM in a
    valid 24-hour range — this function does not re-validate it.
    """
    if len(label) > MAX_REMINDER_LABEL:
        raise ReminderLabelTooLong()
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "SELECT COUNT(*) AS n FROM reminders WHERE user_id = ? AND is_active = TRUE", (uid,))
    if c.fetchone()["n"] >= MAX_ACTIVE_REMINDERS:
        await conn.close()
        raise ReminderLimitReached()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db.db_execute(
        c,
        "INSERT INTO reminders (user_id, label, reminder_time, is_active, repeat_type, created_at) VALUES (?, ?, ?, TRUE, ?, ?) RETURNING id",
        (uid, label, reminder_time, repeat_type, ts),
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
