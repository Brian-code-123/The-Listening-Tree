"""Delete my account and download my data."""
import json
import time
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, Response

from app.core.session import clear_login, get_lang, get_user
from app.db import queries as db
from app.services.auth import MAX_PASSWORD_LENGTH, verify_password_async
from app.services.rate_limit import check_and_increment
from app.services.security_events import record_event

router = APIRouter()

DELETE_LIMIT = 5
DELETE_WINDOW = 600
# A Google account has no password to confirm with, so it must have signed in
# just now instead.
RECENT_LOGIN_SECONDS = 300


@router.post("/auth/delete-account")
async def delete_account(request: Request, password: str = Form("")):
    """Permanently erase the signed-in user and everything they wrote."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    lang = get_lang(request)
    if not await check_and_increment(f"acctdel:{uid}", DELETE_LIMIT, DELETE_WINDOW):
        return JSONResponse({"success": False, "message": "Too many attempts. Please wait a few minutes." if lang == "en" else "嘗試次數過多，請稍後再試"}, status_code=429)

    conn = await db.get_db()
    try:
        c = conn.cursor()
        await db.db_execute(c, "SELECT email, password, auth_provider FROM users WHERE id = ?", (uid,))
        row = c.fetchone()
        if row is None:
            return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)

        password = password.strip()
        if row["auth_provider"] == "google":
            confirmed = time.time() - int(request.session.get("iat", 0)) <= RECENT_LOGIN_SECONDS
            wrong = "Please sign in with Google again, then retry." if lang == "en" else "請重新用 Google 登入，再試一次"
        else:
            confirmed = 0 < len(password) <= MAX_PASSWORD_LENGTH and await verify_password_async(password, row["password"])
            wrong = "Password is incorrect" if lang == "en" else "密碼不正確"
        if not confirmed:
            return JSONResponse({"success": False, "field": "password", "message": wrong}, status_code=403)

        # One transaction: either everything goes or nothing does.
        for sql in (
            "DELETE FROM chat_history WHERE user_id = ?",
            "DELETE FROM conversations WHERE user_id = ?",
            "DELETE FROM reminders WHERE user_id = ?",
            "DELETE FROM preferences WHERE user_id = ?",
            "UPDATE security_events SET user_id = NULL WHERE user_id = ?",
        ):
            await db.db_execute(c, sql, (uid,))
        await db.db_execute(c, "DELETE FROM email_verifications WHERE LOWER(email) = LOWER(?)", (row["email"],))
        # Limiter keys carry the address (login_fail:<email>:<ip>, verify_code:<email>...).
        await db.db_execute(c, "DELETE FROM rate_limit_events WHERE position(? in key) > 0", (row["email"].lower(),))
        await db.db_execute(c, "DELETE FROM users WHERE id = ?", (uid,))
        await conn.commit()
    finally:
        await conn.close()

    clear_login(request)
    await record_event("account_deleted", request=request)
    return JSONResponse({"success": True, "message": "Account deleted" if lang == "en" else "帳戶已刪除"})


@router.get("/account/export")
async def export_account(request: Request):
    """Everything we hold about the signed-in user, as a JSON download."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    conn = await db.get_db()
    try:
        c = conn.cursor()

        async def rows(sql: str):
            await db.db_execute(c, sql, (uid,))
            return [dict(r) for r in c.fetchall()]

        await db.db_execute(c, "SELECT email, username, created_at, last_login, auth_provider, consent_at, consent_version FROM users WHERE id = ?", (uid,))
        profile = c.fetchone()
        conversations = await rows("SELECT id, lang, title, created_at, updated_at, pinned, tag FROM conversations WHERE user_id = ? AND is_deleted = FALSE ORDER BY id")
        messages = await rows("SELECT conversation_id, lang, timestamp, is_bot, message FROM chat_history WHERE user_id = ? AND is_deleted = FALSE ORDER BY id")
        reminders = await rows("SELECT label, reminder_time, is_active, repeat_type, created_at FROM reminders WHERE user_id = ? ORDER BY id")
        preferences = await rows("SELECT pref_key, pref_value FROM preferences WHERE user_id = ? ORDER BY id")
    finally:
        await conn.close()
    if profile is None:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    by_conversation: dict = {}
    for m in messages:
        by_conversation.setdefault(m["conversation_id"], []).append(m)
    for conv in conversations:
        conv["messages"] = by_conversation.get(conv["id"], [])
    payload = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "profile": dict(profile),
        "conversations": conversations,
        "reminders": reminders,
        "preferences": preferences,
    }
    await record_event("data_export", request=request, user_id=uid)
    return Response(
        json.dumps(payload, ensure_ascii=False, default=str, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="listening-tree-data.json"', "Cache-Control": "no-store"},
    )
