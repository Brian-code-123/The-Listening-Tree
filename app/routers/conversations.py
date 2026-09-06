"""Conversation history: list/create/rename/pin/tag conversations, and load
one conversation's messages. Also the shared helpers chat.py uses to resolve
which conversation a new message belongs to.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from app.core import config
from app.core.session import _CONTROL_CHAR_PATTERN, get_lang, get_user
from app.db import queries as db
from translations import TRANSLATIONS, get_text

logger = logging.getLogger(__name__)

ERROR_NOT_AUTHENTICATED = "not authenticated"
ERROR_NOT_FOUND = "not found"

router = APIRouter()


async def get_or_create_active_conversation(cursor, user_id: int, lang: str, requested_id: Optional[int]) -> int:
    """Resolve which conversation a new message belongs to.

    Trusts `requested_id` only if it exists, belongs to this user, and isn't
    deleted; otherwise falls back to the user's most recently updated
    conversation for this language, creating one if they have none yet. This
    keeps callers that don't know about conversations (quick-action buttons
    that POST to /get_response directly) working without any changes.
    """
    if requested_id is not None:
        await db.db_execute(
            cursor,
            "SELECT id FROM conversations WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (requested_id, user_id),
        )
        if cursor.fetchone():
            return requested_id

    await db.db_execute(
        cursor,
        "SELECT id FROM conversations WHERE user_id = ? AND lang = ? AND is_deleted = FALSE ORDER BY updated_at DESC LIMIT 1",
        (user_id, lang),
    )
    row = cursor.fetchone()
    if row:
        return row["id"]

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db.db_execute(
        cursor,
        "INSERT INTO conversations (user_id, lang, created_at, updated_at) VALUES (?, ?, ?, ?) RETURNING id",
        (user_id, lang, ts, ts),
    )
    return cursor.fetchone()["id"]


async def load_conversation_messages(cursor, conn, conversation_id: int, lang: str) -> list:
    """Shared history-loading logic for one conversation.

    Extracted so both the legacy `/get_chat_history` endpoint and the new
    per-conversation endpoint return identical shapes and share the
    stale-greeting cleanup behaviour.
    """
    await db.db_execute(
        cursor,
        "SELECT id, timestamp, is_bot, message FROM chat_history WHERE conversation_id = ? AND is_deleted = FALSE ORDER BY timestamp",
        (conversation_id,),
    )
    rows = cursor.fetchall()

    # A lone bot-authored auto-greeting isn't real conversation content —
    # if it's stuck showing a different language's greeting text (e.g. it
    # was written before the user ever switched language), soft-delete it
    # so it gets recomputed live in the *current* language below, instead
    # of staying frozen in whatever language it was first shown in.
    current_welcome = get_text("welcome_chat", lang)
    if len(rows) == 1 and rows[0]["is_bot"]:
        all_welcome_variants = {get_text("welcome_chat", l) for l in TRANSLATIONS}
        if rows[0]["message"] in all_welcome_variants and rows[0]["message"] != current_welcome:
            await db.db_execute(cursor, "UPDATE chat_history SET is_deleted = TRUE WHERE id = ?", (rows[0]["id"],))
            await conn.commit()
            rows = []

    history = [
        {
            "timestamp": db._json_timestamp(r["timestamp"]),
            "sender": "bot" if r["is_bot"] else "user",
            "message": r["message"],
        }
        for r in rows
    ]

    if not history:
        # Recomputed live (not persisted) so it always matches the
        # current UI language, even across repeated language switches
        # before the user ever sends a real message.
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history = [{"timestamp": ts, "sender": "bot", "message": current_welcome}]

    return history


@router.get("/get_chat_history")
async def get_chat_history(request: Request):
    """Legacy: get history for the user's most recent conversation.

    Kept for callers that don't know about conversations yet (the
    accessibility-mode chat page) — resolves to the same "most recent, or
    create one" conversation that a conversation_id-less /get_response call
    would land in, so both stay in sync.
    """
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"history": []})
    lang = get_lang(request)
    conn = None
    try:
        conn = await db.get_db()
        c = conn.cursor()
        conversation_id = await get_or_create_active_conversation(c, uid, lang, None)
        await conn.commit()
        history = await load_conversation_messages(c, conn, conversation_id, lang)
        return JSONResponse({"history": history})
    except Exception as e:
        # Graceful degradation for transient DB/network failures.
        logger.error(f"[CHAT_HISTORY] fallback due to DB error: {e}")
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return JSONResponse({"history": [{"timestamp": ts, "sender": "bot", "message": get_text("welcome_chat", lang)}], "degraded": True})
    finally:
        if conn is not None:
            await conn.close()


@router.get("/conversations")
async def list_conversations(request: Request):
    """List the current user's conversations for the sidebar, newest first."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"conversations": []})
    lang = get_lang(request)
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(
        c,
        "SELECT id, title, updated_at, pinned, tag FROM conversations "
        "WHERE user_id = ? AND lang = ? AND is_deleted = FALSE "
        "ORDER BY pinned DESC, updated_at DESC",
        (uid, lang),
    )
    conversations = [
        {
            "id": r["id"],
            "title": r["title"] or get_text("new_conversation", lang),
            "updated_at": db._json_timestamp(r["updated_at"]),
            "pinned": bool(r["pinned"]),
            "tag": r["tag"],
        }
        for r in c.fetchall()
    ]
    await conn.close()
    return JSONResponse({"conversations": conversations})


@router.post("/conversations/{conversation_id}/pin")
async def toggle_conversation_pin(request: Request, conversation_id: int):
    """Flip a conversation's pinned state; pinned ones sort first."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": ERROR_NOT_AUTHENTICATED}, status_code=401)
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await db.db_execute(
            c,
            "SELECT pinned FROM conversations WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (conversation_id, uid),
        )
        row = c.fetchone()
        if not row:
            return JSONResponse({"error": ERROR_NOT_FOUND}, status_code=404)
        new_pinned = not row["pinned"]
        await db.db_execute(c, "UPDATE conversations SET pinned = ? WHERE id = ?", (new_pinned, conversation_id))
        await conn.commit()
        return JSONResponse({"pinned": new_pinned})
    finally:
        await conn.close()


@router.post("/conversations/{conversation_id}/tag")
async def set_conversation_tag(request: Request, conversation_id: int, tag: str = Form("")):
    """Set (or clear, with an empty value) a conversation's category tag."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": ERROR_NOT_AUTHENTICATED}, status_code=401)
    tag = tag.strip()
    if tag and tag not in config.CONVERSATION_TAGS:
        return JSONResponse({"error": "invalid tag"}, status_code=400)
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await db.db_execute(
            c,
            "UPDATE conversations SET tag = ? WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (tag or None, conversation_id, uid),
        )
        found = db._safe_rowcount(c) > 0
        await conn.commit()
        if not found:
            return JSONResponse({"error": ERROR_NOT_FOUND}, status_code=404)
        return JSONResponse({"tag": tag or None})
    finally:
        await conn.close()


@router.post("/conversations/{conversation_id}/title")
async def rename_conversation(request: Request, conversation_id: int, title: str = Form(...)):
    """Rename a conversation. An empty result after cleanup falls back to
    the auto-generated title (first-message text) instead of storing blank."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": ERROR_NOT_AUTHENTICATED}, status_code=401)
    lang = get_lang(request)
    cleaned = _CONTROL_CHAR_PATTERN.sub(" ", title)
    cleaned = " ".join(cleaned.split())[:100]
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await db.db_execute(
            c,
            "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ? AND is_deleted = FALSE",
            (cleaned or None, conversation_id, uid),
        )
        found = db._safe_rowcount(c) > 0
        await conn.commit()
        if not found:
            return JSONResponse({"error": ERROR_NOT_FOUND}, status_code=404)
        return JSONResponse({"title": cleaned or get_text("new_conversation", lang)})
    finally:
        await conn.close()


@router.post("/conversations/new")
async def create_conversation(request: Request):
    """Start a new, empty conversation and return its id."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"error": ERROR_NOT_AUTHENTICATED}, status_code=401)
    lang = get_lang(request)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(
        c,
        "INSERT INTO conversations (user_id, lang, created_at, updated_at) VALUES (?, ?, ?, ?) RETURNING id",
        (uid, lang, ts, ts),
    )
    new_id = c.fetchone()["id"]
    # cleanup_old_conversations() (the batch job that normally enforces this
    # cap) only runs from run_periodic_tasks(), which is explicitly skipped
    # on Vercel — so on this deployment target nothing else ever trims a
    # user's conversation count. Enforce the same cap inline, per-write,
    # instead of relying on a background loop that doesn't run here.
    await db.db_execute(
        c,
        "WITH ranked AS ("
        "  SELECT id, ROW_NUMBER() OVER (ORDER BY updated_at DESC, id DESC) AS rn"
        "  FROM conversations WHERE user_id = ? AND lang = ? AND is_deleted = FALSE"
        ") UPDATE conversations SET is_deleted = TRUE WHERE id IN (SELECT id FROM ranked WHERE rn > ?)",
        (uid, lang, config.CONVERSATION_MAX_PER_LANG),
    )
    await conn.commit()
    await conn.close()
    return JSONResponse({"conversation_id": new_id})


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(request: Request, conversation_id: int):
    """Get the message history for one specific conversation."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"history": []}, status_code=401)
    lang = get_lang(request)
    conn = None
    try:
        conn = await db.get_db()
        c = conn.cursor()
        # Ownership check — a conversation_id belonging to another user (or a
        # deleted one) is treated as not found rather than leaking its rows.
        await db.db_execute(c, "SELECT id FROM conversations WHERE id = ? AND user_id = ? AND is_deleted = FALSE", (conversation_id, uid))
        if not c.fetchone():
            return JSONResponse({"history": [], "error": ERROR_NOT_FOUND}, status_code=404)
        history = await load_conversation_messages(c, conn, conversation_id, lang)
        return JSONResponse({"history": history})
    except Exception as e:
        logger.error(f"[CONVERSATIONS] fallback due to DB error: {e}")
        return JSONResponse({"history": [], "degraded": True})
    finally:
        if conn is not None:
            await conn.close()
