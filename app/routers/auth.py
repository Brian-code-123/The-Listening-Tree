"""Auth routes: login/register/logout, Google Sign-In, and the profile
(display name + password) settings that live alongside them.
"""
import builtins as _builtins
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core import config
from app.core.session import _CONTROL_CHAR_PATTERN, get_lang, get_user, tpl_context
from app.core.templates import templates
from app.db import queries as db
from app.services.auth import (
    LOGIN_LOCKOUT_MINUTES,
    LOGIN_MAX_ATTEMPTS,
    hash_password,
    is_password_hashed,
    validate_email,
    validate_password_strength,
    verify_password,
)
from app.services.email import (
    VERIFICATION_CODE_TTL_MINUTES,
    VERIFICATION_RESEND_COOLDOWN_SECONDS,
    generate_verification_code,
    send_verification_email,
)
from app.services.rate_limit import check_and_increment, client_key

# Generous enough for a real user's occasional retry (wrong password, typo'd
# email, browser autofill double-submit), tight enough to slow down
# scripted brute-forcing. Per-IP, 60s fixed window.
LOGIN_RATE_LIMIT = 10
REGISTER_RATE_LIMIT = 5
SEND_CODE_RATE_LIMIT = 5
RATE_LIMIT_WINDOW_SECONDS = 60

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    if get_user(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    lang = get_lang(request)
    google_error = None
    if error == "google_failed":
        google_error = "Google sign-in failed. Please try again or use your password." if lang == 'en' else "Google 登入失敗，請再試一次或用密碼登入"
    return templates.TemplateResponse(
        "login.html",
        tpl_context(request, error=google_error, google_enabled=config.GOOGLE_LOGIN_ENABLED),
    )


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[str] = Form(None),
):
    """Authenticate user login with email and password credentials.

    Sets session values on successful authentication:
      - session['user_id']: Database row ID
      - session['user_email']: User email address
      - session['remember_me']: whether the session cookie should persist (90 days) or expire with the browser session
      - session['language']: User's preferred language (loaded from preferences table)

    Failed attempts are tracked per account (`users.failed_login_attempts` /
    `locked_until`) and lock the account for LOGIN_LOCKOUT_MINUTES after
    LOGIN_MAX_ATTEMPTS consecutive failures, to slow down brute-force guessing.

    Args:
        request: HTTP request object with session middleware
        email: User email (matched case-insensitively against the stored address)
        password: User password, verified against the PBKDF2-HMAC-SHA256 hash
        remember_me: Present (any value) when the "remember me" checkbox was checked

    Returns:
        HTMLResponse: Redirect to / (home) on success, or login.html with error message on failure
    """
    lang = get_lang(request)
    if not await check_and_increment(client_key(request, "login"), LOGIN_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS):
        too_many_msg = "Too many login attempts. Please wait a moment and try again." if lang == 'en' else "登入嘗試次數過多，請稍等再試"
        return templates.TemplateResponse("login.html", tpl_context(request, error=too_many_msg, google_enabled=config.GOOGLE_LOGIN_ENABLED), status_code=429)
    email = email.strip().lower()
    password = password.strip()
    generic_error = "Invalid email or password" if lang == 'en' else "電郵或密碼錯誤"
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(
        c,
        "SELECT id, email, password, failed_login_attempts, locked_until FROM users WHERE LOWER(email) = LOWER(?)",
        (email,),
    )
    user = c.fetchone()

    if user and user["locked_until"] and user["locked_until"] > datetime.now():
        await conn.close()
        wait_minutes = max(1, int((user["locked_until"] - datetime.now()).total_seconds() // 60) + 1)
        locked_msg = (
            f"Too many failed attempts. Try again in {wait_minutes} min." if lang == 'en'
            else f"登入失敗次數過多，請 {wait_minutes} 分鐘後再試"
        )
        return templates.TemplateResponse("login.html", tpl_context(request, error=locked_msg, google_enabled=config.GOOGLE_LOGIN_ENABLED), status_code=429)

    if user and verify_password(password, user["password"]):
        if not is_password_hashed(user["password"]):
            # Transparent migration for legacy plaintext rows.
            await db.db_execute(c, "UPDATE users SET password = ? WHERE id = ?", (hash_password(password), user["id"]))
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.db_execute(
            c,
            "UPDATE users SET last_login = ?, failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (ts, user["id"]),
        )
        await conn.commit()
        request.session['user_email'] = user["email"]
        request.session['user_id'] = user["id"]
        request.session['remember_me'] = bool(remember_me)
        # Load language preference
        await db.db_execute(c, "SELECT pref_value FROM preferences WHERE user_id = ? AND pref_key = 'language'", (user["id"],))
        pref = c.fetchone()
        if pref:
            request.session['language'] = pref["pref_value"]
        await conn.close()
        return RedirectResponse(url="/", status_code=303)

    if user:
        attempts = (user["failed_login_attempts"] or 0) + 1
        if attempts >= LOGIN_MAX_ATTEMPTS:
            locked_until = (datetime.now() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
            await db.db_execute(
                c,
                "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, locked_until, user["id"]),
            )
        else:
            await db.db_execute(c, "UPDATE users SET failed_login_attempts = ? WHERE id = ?", (attempts, user["id"]))
        await conn.commit()
    await conn.close()
    return templates.TemplateResponse("login.html", tpl_context(request, error=generic_error, google_enabled=config.GOOGLE_LOGIN_ENABLED))


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if get_user(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("register.html", tpl_context(request))


@router.post("/send_verification_code")
async def send_verification_code(request: Request):
    """Generate and email a 6-digit verification code for registration.

    Body: JSON {"email": str}
    Returns JSON {"success": bool, "message": str}
    """
    lang = get_lang(request)
    if not await check_and_increment(client_key(request, "send_verification_code"), SEND_CODE_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS):
        return JSONResponse(
            {"success": False, "message": "Too many requests. Please wait a moment and try again." if lang == 'en' else "請求次數過多，請稍等再試"},
            status_code=429,
        )
    try:
        body = await request.json()
    except Exception:
        body = {}
    email = str(body.get("email", "")).strip().lower()

    is_valid_email, _ = validate_email(email)
    if not is_valid_email:
        return JSONResponse(
            {"success": False, "message": "Invalid email format" if lang == 'en' else "電郵格式無效"},
            status_code=400,
        )

    conn = await db.get_db()
    c = conn.cursor()
    try:
        await db.db_execute(c, "SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        if c.fetchone():
            await conn.close()
            return JSONResponse(
                {"success": False, "message": "Email already registered" if lang == 'en' else "電郵已註冊"},
                status_code=400,
            )

        await db.db_execute(
            c,
            "SELECT created_at FROM email_verifications WHERE LOWER(email) = LOWER(?) ORDER BY created_at DESC LIMIT 1",
            (email,),
        )
        last = c.fetchone()
        if last and (datetime.now() - last["created_at"]).total_seconds() < VERIFICATION_RESEND_COOLDOWN_SECONDS:
            await conn.close()
            return JSONResponse(
                {"success": False, "message": "Please wait before requesting another code" if lang == 'en' else "請稍等先再發送驗證碼"},
                status_code=429,
            )

        code = generate_verification_code()
        ts = datetime.now()
        expires_at = ts.timestamp() + VERIFICATION_CODE_TTL_MINUTES * 60
        expires_at_str = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
        await db.db_execute(
            c,
            "INSERT INTO email_verifications (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (email, code, expires_at_str, ts.strftime('%Y-%m-%d %H:%M:%S')),
        )
        await conn.commit()
        await conn.close()

        sent = send_verification_email(email, code, lang)
        if not sent:
            return JSONResponse(
                {"success": False, "message": "Failed to send verification email" if lang == 'en' else "驗證碼郵件發送失敗"},
                status_code=500,
            )
        return JSONResponse({"success": True, "message": "Verification code sent" if lang == 'en' else "驗證碼已發送"})
    except Exception as e:
        await conn.close()
        _builtins._original_print(f"[ERROR] send_verification_code failed: {e}")
        return JSONResponse(
            {"success": False, "message": "Service temporarily unavailable" if lang == 'en' else "服務暫時不可用"},
            status_code=500,
        )


@router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    verification_code: str = Form(...),
):
    """Create a new user account (registration).

    Validation steps:
      1. Email format validation (RFC 5322 basic pattern)
      2. Password strength validation (min 8 characters)
      3. Confirm password == password (client-side + server-side check)
      4. Verification code must match an unused, unexpired code sent to this email
      5. Email must be unique (PostgreSQL UNIQUE constraint)
      6. Password stored with PBKDF2-HMAC-SHA256

    On success: Inserts new user row, creates authenticated session, redirects to /.
    On failure: Returns register.html with localized error message (or JSON if
    the request declares it wants a JSON response, for the AJAX form flow).

    Args:
        request: HTTP request object
        email: Email address (must not exist in users table)
        password: Password in plaintext (min 8 chars)
        confirm_password: Confirmation password (must == password)
        verification_code: 6-digit code sent to email via /send_verification_code

    Returns:
        HTMLResponse: Redirect to / on success, or register.html with error on failure
    """
    lang = get_lang(request)
    wants_json = "application/json" in request.headers.get("accept", "")

    def fail(message: str, field: str = "email", status_code: int = 400):
        if wants_json:
            return JSONResponse({"success": False, "field": field, "message": message}, status_code=status_code)
        return templates.TemplateResponse("register.html", tpl_context(request, error=message))

    if not await check_and_increment(client_key(request, "register"), REGISTER_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS):
        too_many_msg = "Too many attempts. Please wait a moment and try again." if lang == 'en' else "嘗試次數過多，請稍等再試"
        if wants_json:
            return JSONResponse({"success": False, "field": "email", "message": too_many_msg}, status_code=429)
        return templates.TemplateResponse("register.html", tpl_context(request, error=too_many_msg), status_code=429)

    email = email.strip().lower()
    password = password.strip()
    confirm_password = confirm_password.strip()
    verification_code = verification_code.strip()

    # Validate email format
    is_valid_email, email_error = validate_email(email)
    if not is_valid_email:
        return fail("Invalid email format" if lang == 'en' else "電郵格式無效", field="email")

    # Validate password strength
    is_valid_password, password_error = validate_password_strength(password)
    if not is_valid_password:
        return fail("Password must be at least 8 characters" if lang == 'en' else "密碼最少需要 8 個字元", field="password")

    # Validate password confirmation
    if password != confirm_password:
        return fail("Passwords do not match" if lang == 'en' else "密碼唔一致", field="confirm_password")

    conn = await db.get_db()
    c = conn.cursor()
    try:
        # Validate verification code
        await db.db_execute(
            c,
            "SELECT id FROM email_verifications WHERE LOWER(email) = LOWER(?) AND code = ? AND used = FALSE AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
            (email, verification_code, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        )
        verification = c.fetchone()
        if not verification:
            await conn.close()
            return fail("Verification code is incorrect or has expired" if lang == 'en' else "驗證碼錯誤或已過期", field="verification_code")

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.db_execute(c, "INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)", (email, hash_password(password), ts))
        await db.db_execute(c, "UPDATE email_verifications SET used = TRUE WHERE id = ?", (verification["id"],))
        await conn.commit()
        await db.db_execute(c, "SELECT id, email, password FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        created_user = c.fetchone()
        if created_user:
            request.session['user_email'] = created_user["email"]
            request.session['user_id'] = created_user["id"]
            request.session['remember_me'] = True
        await conn.close()
        if wants_json:
            return JSONResponse({"success": True, "redirect": "/"})
        return RedirectResponse(url="/", status_code=303)
    except db.PgIntegrityError:
        await conn.close()
        return fail("Email already exists" if lang == 'en' else "電郵已存在", field="email")
    except Exception as e:
        await conn.close()
        _builtins._original_print(f"[ERROR] Registration failed: {e}")
        return fail(
            "Service temporarily unavailable. Your account data remains in database; please try again."
            if lang == 'en'
            else "服務暫時不可用。帳號資料會保留喺資料庫，請稍後再試。",
            field="email",
            status_code=500,
        )


@router.get("/auth/google")
async def google_login(request: Request):
    """Redirect to Google's consent screen. 404s if Google sign-in isn't configured."""
    if not config.GOOGLE_LOGIN_ENABLED:
        raise HTTPException(status_code=404)
    redirect_uri = config.GOOGLE_REDIRECT_URI or str(request.url_for("google_callback"))
    return await config.oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    """Handle Google's redirect back: verify the ID token, then find-or-create
    the local user and log them in the same way /login does.

    Matching order: first by google_id (returning Google user), then by
    email (auto-link an existing password account — Google already verified
    ownership of that email), otherwise create a brand-new account with a
    random, never-typeable password hash.
    """
    if not config.GOOGLE_LOGIN_ENABLED:
        raise HTTPException(status_code=404)

    from authlib.integrations.base_client.errors import OAuthError

    try:
        token = await config.oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(url="/login?error=google_failed", status_code=303)

    userinfo = token.get("userinfo") or {}
    google_id = userinfo.get("sub")
    email = (userinfo.get("email") or "").strip().lower()
    if not google_id or not email or not userinfo.get("email_verified"):
        return RedirectResponse(url="/login?error=google_failed", status_code=303)

    display_name = _CONTROL_CHAR_PATTERN.sub(" ", userinfo.get("name") or "")
    display_name = " ".join(display_name.split())[:50]

    conn = await db.get_db()
    c = conn.cursor()
    try:
        await db.db_execute(c, "SELECT id, email FROM users WHERE google_id = ?", (google_id,))
        user = c.fetchone()

        if not user:
            await db.db_execute(c, "SELECT id, email, google_id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            existing = c.fetchone()
            if existing and existing["google_id"]:
                # Email matches, but already linked to a different Google account.
                await conn.close()
                return RedirectResponse(url="/login?error=google_failed", status_code=303)
            if existing:
                await db.db_execute(c, "UPDATE users SET google_id = ?, auth_provider = 'google' WHERE id = ?", (google_id, existing["id"]))
                user = existing
            else:
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                synthetic_password = hash_password(secrets.token_hex(32))
                await db.db_execute(
                    c,
                    "INSERT INTO users (email, password, username, google_id, auth_provider, created_at) VALUES (?, ?, ?, ?, 'google', ?)",
                    (email, synthetic_password, display_name or None, google_id, ts),
                )
                await db.db_execute(c, "SELECT id, email FROM users WHERE google_id = ?", (google_id,))
                user = c.fetchone()

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.db_execute(c, "UPDATE users SET last_login = ? WHERE id = ?", (ts, user["id"]))
        await conn.commit()
        request.session['user_email'] = user["email"]
        request.session['user_id'] = user["id"]
        request.session['remember_me'] = True
    finally:
        await conn.close()

    return RedirectResponse(url="/", status_code=303)


@router.get("/forgot_password")
async def forgot_password(request: Request):
    return RedirectResponse(url="/login", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ---------------------------------------------------------------------------
# Profile — display name + password
# ---------------------------------------------------------------------------
@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "SELECT username, email FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    await conn.close()
    return templates.TemplateResponse(
        "profile.html",
        tpl_context(
            request,
            display_name=(user_row["username"] if user_row else None) or "",
            email=user_row["email"] if user_row else "",
        ),
    )


@router.post("/profile/name")
async def update_profile_name(request: Request, display_name: str = Form(...)):
    """Update the user's display name, shown in chat headers and used to
    let the AI address them by name (see call_ai's `display_name` param)."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    lang = get_lang(request)

    # Strip control characters and collapse whitespace — this value is later
    # interpolated directly into the LLM system prompt in call_ai(), so it
    # must never be able to smuggle in newlines or a fake "SYSTEM:" line.
    cleaned = _CONTROL_CHAR_PATTERN.sub(" ", display_name)
    cleaned = " ".join(cleaned.split())[:50]

    if not cleaned:
        return JSONResponse(
            {"success": False, "field": "display_name", "message": "Please enter a name" if lang == 'en' else "請輸入名稱"},
            status_code=400,
        )

    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "UPDATE users SET username = ? WHERE id = ?", (cleaned, uid))
    await conn.commit()
    await conn.close()
    return JSONResponse({"success": True, "display_name": cleaned, "message": "Name updated" if lang == 'en' else "名稱已更新"})


@router.post("/profile/password")
async def update_profile_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_new_password: str = Form(...),
):
    """Change the user's password, gated on confirming the current one."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False, "message": "Not authenticated"}, status_code=401)
    lang = get_lang(request)

    def fail(message: str, field: str, status_code: int = 400):
        return JSONResponse({"success": False, "field": field, "message": message}, status_code=status_code)

    current_password = current_password.strip()
    new_password = new_password.strip()
    confirm_new_password = confirm_new_password.strip()

    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "SELECT password FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    if not user_row or not verify_password(current_password, user_row["password"]):
        await conn.close()
        return fail("Current password is incorrect" if lang == 'en' else "現時密碼不正確", field="current_password")

    is_valid_password, _ = validate_password_strength(new_password)
    if not is_valid_password:
        await conn.close()
        return fail("Password must be at least 8 characters" if lang == 'en' else "密碼最少需要 8 個字元", field="new_password")

    if new_password != confirm_new_password:
        await conn.close()
        return fail("Passwords do not match" if lang == 'en' else "密碼唔一致", field="confirm_new_password")

    await db.db_execute(c, "UPDATE users SET password = ? WHERE id = ?", (hash_password(new_password), uid))
    await conn.commit()
    await conn.close()
    return JSONResponse({"success": True, "message": "Password updated" if lang == 'en' else "密碼已更新"})
