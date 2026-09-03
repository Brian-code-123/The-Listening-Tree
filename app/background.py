"""Background periodic task loop and the housekeeping jobs it drives —
reminder checks, chat/conversation cleanup, and reminder auto-expiry.

Skipped entirely on Vercel (see `app/main.py`'s lifespan) since serverless
functions can't run a perpetual loop.
"""
import asyncio
import logging
from datetime import datetime

from app.core import config
from app.db import queries as db
from app.services.rate_limit import cleanup_old_rate_limit_events

logger = logging.getLogger(__name__)


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
            # connection never returns to the pool, and the pool's own close()
            # then hangs waiting for it (reproduced while testing this migration).
            conn = await db.get_db()
            try:
                c = conn.cursor()
                query = (
                    "SELECT u.email, r.label, r.reminder_time FROM reminders r "
                    "JOIN users u ON r.user_id = u.id "
                    "WHERE r.is_active = TRUE AND DATE(r.created_at) = ?"
                )
                await db.db_execute(c, query, (today,))
                for row in c.fetchall():
                    email = row["email"]
                    label = row["label"]
                    rtime = row["reminder_time"]
                    if rtime == current_time:
                        # In a real app, this would trigger a push notification or WebSocket msg
                        logger.info(f"[REMINDER] {email}: {label} at {rtime}")
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
                await cleanup_old_rate_limit_events()

        except asyncio.CancelledError:
            # Allow graceful shutdown to stop this task immediately.
            raise

        except Exception as e:
            logger.error(f"periodic_tasks: {e}")

        await asyncio.sleep(60)


async def cleanup_old_conversations() -> None:
    """Soft-delete whole conversations beyond the per-user/language cap.

    Runs before the per-conversation message cleanup below so that a
    conversation slated for removal doesn't also cost a message-level pass.
    Caps by *conversation count*, not message count — an old conversation is
    dropped wholesale rather than gutted message-by-message, so it either
    fully exists or fully doesn't in the sidebar list.
    """
    conn = await db.get_db()
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
            (config.CONVERSATION_MAX_PER_LANG,),
        )
        deleted_count = db._safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    if deleted_count > 0:
        logger.info(f"[CLEANUP] Marked {deleted_count} old conversations as deleted")


async def cleanup_old_chat_history() -> None:
    """Soft-delete oldest chat rows beyond the per-conversation cap.

    Partitioned by conversation_id (not user_id/lang) so a long-running
    conversation can't crowd out messages belonging to a different,
    still-listed conversation for the same user.
    """
    conn = await db.get_db()
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
            (config.CHAT_HISTORY_MAX_MESSAGES_PER_LANG,),
        )
        deleted_count = db._safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    if deleted_count > 0:
        logger.info(f"[CLEANUP] Marked {deleted_count} old chat rows as deleted")


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
        (conversation_id, config.CHAT_HISTORY_MAX_MESSAGES_PER_LANG, conversation_id),
    )


async def auto_expire_old_reminders() -> None:
    """Deactivate reminders created before today.

    Runs once per hour (top of the hour) from the background thread.
    """
    conn = await db.get_db()
    try:
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.db_execute(
            c,
            "UPDATE reminders SET is_active = FALSE, updated_at = ? "
            "WHERE DATE(created_at) < ? AND is_active = TRUE",
            (ts, today),
        )
        expired = db._safe_rowcount(c)
        await conn.commit()
    finally:
        await conn.close()
    if expired > 0:
        logger.info(f"[EXPIRE] Marked {expired} old reminders as inactive")
