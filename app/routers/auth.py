"""Auth routes: login/register/logout, Google Sign-In, and the profile
(display name + password) settings that live alongside them.
"""
import asyncio
import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core import config
from app.core.session import _CONTROL_CHAR_PATTERN, clear_login, get_lang, get_user, start_session, tpl_context
from app.core.templates import templates
from app.db import queries as db
from app.services.auth import (
    MAX_PASSWORD_LENGTH,
    code_digest,
    dummy_hash,
    hash_password_async,
    needs_rehash,
    validate_email,
    validate_password_strength,
    verify_password_async,
)
from app.services.email import (
    VERIFICATION_CODE_TTL_MINUTES,
    VERIFICATION_RESEND_COOLDOWN_SECONDS,
    generate_verification_code,
    send_verification_email,
)

from app.services.rate_limit import check_and_increment, client_ip, client_key, hit, reset_key
from app.services.security_events import record_event

logger = logging.getLogger(__name__)

def _password_error(password: str, lang: str) -> Optional[str]:
    """Localized reason a new password is unacceptable, or None."""
    ok, _ = validate_password_strength(password)
    if ok:
        return None
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters" if lang == 'en' else f"密碼最多 {MAX_PASSWORD_LENGTH} 個字元"
    return "Password must be at least 8 characters" if lang == 'en' else "密碼最少需要 8 個字元"


# Generous enough for a real user's occasional retry (wrong password, typo'd
# email, browser autofill double-submit), tight enough to slow down
# scripted brute-forcing. Per-IP, 60s fixed window.
LOGIN_RATE_LIMIT = 10
REGISTER_RATE_LIMIT = 5
SEND_CODE_RATE_LIMIT = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# Failed-login budget. Counted per email *and* client address, so someone
# guessing from one address cannot lock the real owner out from another, and
# the window simply ends (no stored "locked until" that a stray typo can
# re-arm). The per-email ceiling is higher: it only bounds guessing spread
# thinly across many addresses.
# Verification codes: one send per address per cooldown, a daily cap, and a
# guess budget per address so a 6-digit code cannot be brute-forced.
SEND_CODE_EMAIL_LIMIT = 1
SEND_CODE_DAY_LIMIT = 10
SEND_CODE_DAY_WINDOW = 24 * 60 * 60
VERIFY_CODE_LIMIT = 5
VERIFY_CODE_WINDOW = 10 * 60
PASSWORD_CHANGE_LIMIT = 5
PASSWORD_CHANGE_WINDOW = 10 * 60
LOGIN_FAIL_LIMIT = 5
LOGIN_FAIL_WINDOW = 15 * 60
LOGIN_EMAIL_GLOBAL_LIMIT = 30

LOGIN_PATH = "/login"
REGISTER_TEMPLATE = "register.html"

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


# /auth/login is the path the Next.js pages POST to. It has to differ from
# the page path: in production vercel.json rewrites GET /login to the
# Next.js service, and a rewrite applies to every method, so a POST to
# /login reaches the static page and comes back 405. /login stays
# registered for the existing tests and the (now unrouted) Jinja form.
async def _complete_successful_login(cursor, conn, request: Request, user, password: str, remember_me) -> None:
    """Sign the user in and load their language.

    Takes the caller's cursor and connection; login_post owns the
    connection's lifetime.
    """
    if needs_rehash(user["password"]):
        # The stored hash predates the current cost; replace it while we hold the plaintext.
        await db.db_execute(cursor, "UPDATE users SET password = ? WHERE id = ?", (await hash_password_async(password), user["id"]))
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db.db_execute(
        cursor,
        "UPDATE users SET last_login = ? WHERE id = ?",
        (ts, user["id"]),
    )
    await conn.commit()
    start_session(request, user_id=user["id"], email=user["email"], session_version=user["session_version"] or 0, remember_me=bool(remember_me))
    await db.db_execute(cursor, "SELECT pref_value FROM preferences WHERE user_id = ? AND pref_key = 'language'", (user["id"],))
    pref = cursor.fetchone()
    if pref:
        request.session['language'] = pref["pref_value"]


@router.post("/auth/login", response_class=HTMLResponse)
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

    Attempts are counted atomically per email + client address before the
    password is checked (LOGIN_FAIL_LIMIT per LOGIN_FAIL_WINDOW) and the count
    is cleared by a successful login; see the rate_limit service.

    Args:
        request: HTTP request object with session middleware
        email: User email (matched case-insensitively against the stored address)
        password: User password, verified against the PBKDF2-HMAC-SHA256 hash
        remember_me: Present (any value) when the "remember me" checkbox was checked

    Returns:
        HTMLResponse: Redirect to / (home) on success, or login.html with error message on failure.
        JSONResponse: if the request declares `Accept: application/json` (the
        Next.js login page), mirroring /register's {success, message} / 429
        / {success: true, redirect} contract instead of re-rendering HTML.
    """
    lang = get_lang(request)
    wants_json = "application/json" in request.headers.get("accept", "")

    def fail(message: str, status_code: int = 200):
        if wants_json:
            return JSONResponse({"success": False, "message": message}, status_code=status_code)
        return templates.TemplateResponse(
            "login.html", tpl_context(request, error=message, google_enabled=config.GOOGLE_LOGIN_ENABLED), status_code=status_code
        )

    if not await check_and_increment(client_key(request, "login"), LOGIN_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS):
        too_many_msg = "Too many login attempts. Please wait a moment and try again." if lang == 'en' else "登入嘗試次數過多，請稍等再試"
        return fail(too_many_msg, status_code=429)
    email = email.strip().lower()
    password = password.strip()
    generic_error = "Invalid email or password" if lang == 'en' else "電郵或密碼錯誤"
    fail_key = f"login_fail:{email}:{client_ip(request)}"
    email_key = f"login_fail_email:{email}"
    # Count the attempt *before* spending a password hash on it: the increment
    # is one atomic statement, so parallel guesses cannot all read the same
    # value, and a refused attempt costs the server almost nothing.
    attempts = await hit(fail_key, LOGIN_FAIL_WINDOW)
    email_attempts = await hit(email_key, LOGIN_FAIL_WINDOW)
    if attempts > LOGIN_FAIL_LIMIT or email_attempts > LOGIN_EMAIL_GLOBAL_LIMIT:
        if attempts == LOGIN_FAIL_LIMIT + 1 or email_attempts == LOGIN_EMAIL_GLOBAL_LIMIT + 1:
            # Once per lock, not once per refused attempt, so an attack cannot flood the table.
            await record_event("login_locked", request=request, email=email)
        # Same answer whether or not the account exists.
        locked_msg = (
            "Too many failed attempts. Please wait 15 minutes and try again." if lang == 'en'
            else "登入失敗次數過多，請 15 分鐘後再試"
        )
        return fail(locked_msg, status_code=429)
    # Never hold a pooled connection while asking for another (reset_key and
    # record_event each take their own) or while hashing: with every connection
    # held by a request waiting for a second, the pool deadlocks. So the lookup,
    # the hash check and the sign-in write each borrow a connection in turn.
    conn = await db.get_db()
    try:
        c = conn.cursor()
        await db.db_execute(c, "SELECT id, email, password, session_version, is_active FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        user = c.fetchone()
    finally:
        await conn.close()
    if user and user["is_active"] is False:
        user = None  # a disabled account answers exactly like an unknown one

    # An unknown email still verifies against a throwaway hash, so how long
    # the answer takes does not reveal whether the account exists.
    if len(password) > MAX_PASSWORD_LENGTH:
        await record_event("login_failure", request=request, email=email, user_id=user["id"] if user else None, detail={"reason": "too_long"})
        return fail(generic_error)  # cannot be anyone's password, so do not hash it
    if await verify_password_async(password, user["password"] if user else dummy_hash()) and user:
        conn = await db.get_db()
        try:
            await _complete_successful_login(conn.cursor(), conn, request, user, password, remember_me)
        finally:
            await conn.close()
        await reset_key(fail_key)
        await record_event("login_success", request=request, email=email, user_id=user["id"])
        if wants_json:
            return JSONResponse({"success": True, "redirect": "/"})
        return RedirectResponse(url="/", status_code=303)

    await record_event(
        "login_failure", request=request, email=email, user_id=user["id"] if user else None,
        detail={"reason": "bad_password" if user else "unknown_email"},
    )
    return fail(generic_error)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if get_user(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(REGISTER_TEMPLATE, tpl_context(request))


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

    # Limits first, and for every address: if only unregistered addresses ever hit
    # a 429, the limiter itself would tell an attacker which ones are taken.
    if not await check_and_increment(f"send_code_email:{email}", SEND_CODE_EMAIL_LIMIT, VERIFICATION_RESEND_COOLDOWN_SECONDS):
        return JSONResponse(
            {"success": False, "message": "Please wait before requesting another code" if lang == 'en' else "請稍等先再發送驗證碼"},
            status_code=429,
        )
    if not await check_and_increment(f"send_code_day:{email}", SEND_CODE_DAY_LIMIT, SEND_CODE_DAY_WINDOW):
        return JSONResponse(
            {"success": False, "message": "Too many codes requested for this email today. Please try again tomorrow." if lang == 'en' else "今日為呢個電郵要求驗證碼太多次，請明天再試"},
            status_code=429,
        )

    sent_message = "Verification code sent" if lang == 'en' else "驗證碼已發送"
    conn = await db.get_db()
    c = conn.cursor()
    try:
        await db.db_execute(c, "SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        if c.fetchone():
            # Same answer as for a free address, and nothing is sent, so this
            # endpoint cannot be used to find out who has an account.
            await conn.close()
            return JSONResponse({"success": True, "message": sent_message})

        code = generate_verification_code()
        ts = datetime.now()
        expires_at = ts.timestamp() + VERIFICATION_CODE_TTL_MINUTES * 60
        expires_at_str = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
        # A new code retires the older ones, so only one guessable value is live.
        await db.db_execute(c, "UPDATE email_verifications SET used = TRUE WHERE LOWER(email) = LOWER(?) AND used = FALSE", (email,))
        await db.db_execute(
            c,
            "INSERT INTO email_verifications (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (email, code_digest(email, code), expires_at_str, ts.strftime('%Y-%m-%d %H:%M:%S')),
        )
        await conn.commit()
        await conn.close()

        sent = await asyncio.to_thread(send_verification_email, email, code, lang)
        if not sent:
            return JSONResponse(
                {"success": False, "message": "Failed to send verification email" if lang == 'en' else "驗證碼郵件發送失敗"},
                status_code=500,
            )
        await record_event("code_sent", request=request, email=email)
        return JSONResponse({"success": True, "message": sent_message})
    except Exception as e:
        await conn.close()
        logger.error(f"send_verification_code failed: {e}")
        return JSONResponse(
            {"success": False, "message": "Service temporarily unavailable" if lang == 'en' else "服務暫時不可用"},
            status_code=500,
        )


def _validate_registration_fields(email: str, password: str, confirm_password: str, lang: str) -> Optional[tuple[str, str]]:
    """First failing field check as (message, field), or None if all pass.

    Only the checks that need no database — the verification code and the
    email-uniqueness constraint stay with the registration handler, which
    owns the connection.
    """
    is_valid_email, _ = validate_email(email)
    if not is_valid_email:
        return ("Invalid email format" if lang == 'en' else "電郵格式無效", "email")

    password_error = _password_error(password, lang)
    if password_error:
        return (password_error, "password")

    if password != confirm_password:
        return ("Passwords do not match" if lang == 'en' else "密碼唔一致", "confirm_password")

    return None


# Same page-path collision as /auth/login above.
async def _find_valid_verification(cursor, email: str, verification_code: str):
    """Return the newest unused, unexpired verification row for this email and
    code, or None if the code doesn't check out.
    """
    await db.db_execute(
        cursor,
        "SELECT id FROM email_verifications WHERE LOWER(email) = LOWER(?) AND code = ? AND used = FALSE AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
        (email, code_digest(email, verification_code), datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
    )
    return cursor.fetchone()


async def _create_user_and_start_session(cursor, conn, request: Request, email: str, password: str, verification_id) -> None:
    """Insert the user, burn the verification code, and sign them in.

    Takes the caller's cursor and connection: register_post owns the
    connection's lifetime (it closes it in a finally), so this must not open
    one of its own.
    """
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await db.db_execute(cursor, "INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)", (email, await hash_password_async(password), ts))
    await db.db_execute(cursor, "UPDATE email_verifications SET used = TRUE WHERE id = ?", (verification_id,))
    await conn.commit()
    await db.db_execute(cursor, "SELECT id, email, password FROM users WHERE LOWER(email) = LOWER(?)", (email,))
    created_user = cursor.fetchone()
    if created_user:
        await db.db_execute(
            cursor,
            "UPDATE users SET consent_at = ?, consent_version = ? WHERE id = ?",
            (ts, config.PRIVACY_NOTICE_VERSION, created_user["id"]),
        )
        await conn.commit()
        start_session(request, user_id=created_user["id"], email=created_user["email"], session_version=0, remember_me=True)


@router.post("/auth/register", response_class=HTMLResponse)
@router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    verification_code: str = Form(...),
    consent: str = Form(""),
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
        return templates.TemplateResponse(REGISTER_TEMPLATE, tpl_context(request, error=message))

    if not await check_and_increment(client_key(request, "register"), REGISTER_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS):
        too_many_msg = "Too many attempts. Please wait a moment and try again." if lang == 'en' else "嘗試次數過多，請稍等再試"
        if wants_json:
            return JSONResponse({"success": False, "field": "email", "message": too_many_msg}, status_code=429)
        return templates.TemplateResponse(REGISTER_TEMPLATE, tpl_context(request, error=too_many_msg), status_code=429)

    if consent.strip().lower() not in {"true", "on", "1", "yes"}:
        return fail(
            "Please agree to the privacy notice to register" if lang == 'en' else "請先同意私隱聲明才可註冊",
            field="consent",
        )

    email = email.strip().lower()
    password = password.strip()
    confirm_password = confirm_password.strip()
    verification_code = verification_code.strip()

    field_error = _validate_registration_fields(email, password, confirm_password, lang)
    if field_error is not None:
        message, field = field_error
        return fail(message, field=field)

    verify_key = f"verify_code:{email}"
    if not await check_and_increment(verify_key, VERIFY_CODE_LIMIT, VERIFY_CODE_WINDOW):
        return fail(
            "Too many incorrect codes. Please wait a few minutes and request a new code." if lang == 'en' else "驗證碼錯誤次數過多，請稍後再要求新驗證碼",
            field="verification_code",
            status_code=429,
        )
    # One pooled connection at a time (see login_post): reset_key and record_event
    # borrow their own, so none may be held while they run.
    try:
        conn = await db.get_db()
        try:
            verification = await _find_valid_verification(conn.cursor(), email, verification_code)
        finally:
            await conn.close()
        if not verification:
            await record_event("code_failed", request=request, email=email)
            return fail("Verification code is incorrect or has expired" if lang == 'en' else "驗證碼錯誤或已過期", field="verification_code")

        conn = await db.get_db()
        try:
            await _create_user_and_start_session(conn.cursor(), conn, request, email, password, verification["id"])
        finally:
            await conn.close()
        await reset_key(verify_key)
        await record_event("register", request=request, email=email, user_id=request.session.get("user_id"))
        if wants_json:
            return JSONResponse({"success": True, "redirect": "/"})
        return RedirectResponse(url="/", status_code=303)
    except db.PgIntegrityError:
        return fail("Email already exists" if lang == 'en' else "電郵已存在", field="email")
    except Exception as e:
        # The exception text can carry the address or database detail, so log only its type.
        logger.error("Registration failed (%s)", type(e).__name__)
        return fail(
            "Service temporarily unavailable. Please try again in a moment."
            if lang == 'en'
            else "服務暫時不可用，請稍後再試。",
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


class _GoogleAccountConflict(Exception):
    """The Google email matches a local account already linked elsewhere."""


async def _resolve_or_create_google_user(c, google_id: str, email: str, display_name: str):
    """Find the user behind a Google identity, creating them if needed.

    Returns (user, event): `event` is the security event to record
    ("google_login" or "google_link"). Works on the caller's cursor and never
    opens or closes a connection — google_callback owns that. A disabled
    account is refused like a conflict.
    """
    await db.db_execute(c, "SELECT id, email, session_version, is_active FROM users WHERE google_id = ?", (google_id,))
    user = c.fetchone()
    if user:
        if user["is_active"] is False:
            raise _GoogleAccountConflict()
        return user, "google_login"

    await db.db_execute(c, "SELECT id, email, google_id, session_version, is_active FROM users WHERE LOWER(email) = LOWER(?)", (email,))
    existing = c.fetchone()
    if existing and (existing["google_id"] or existing["is_active"] is False):
        raise _GoogleAccountConflict()

    if existing:
        # The password stays usable: whoever registered it proved they own the
        # mailbox, the same proof Google just gave. But sessions opened before
        # the link are ended, so linking never leaves an older session behind.
        await db.db_execute(
            c,
            "UPDATE users SET google_id = ?, auth_provider = 'google', session_version = session_version + 1 WHERE id = ? RETURNING session_version",
            (google_id, existing["id"]),
        )
        new_version = c.fetchone()["session_version"]
        return {"id": existing["id"], "email": existing["email"], "session_version": new_version}, "google_link"

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    synthetic_password = await hash_password_async(secrets.token_hex(32))
    await db.db_execute(
        c,
        "INSERT INTO users (email, password, username, google_id, auth_provider, created_at) VALUES (?, ?, ?, ?, 'google', ?)",
        (email, synthetic_password, display_name or None, google_id, ts),
    )
    await db.db_execute(c, "SELECT id, email, session_version FROM users WHERE google_id = ?", (google_id,))
    return c.fetchone(), "google_login"


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
        return RedirectResponse(url=f"{LOGIN_PATH}?error=google_failed", status_code=303)

    userinfo = token.get("userinfo") or {}
    google_id = userinfo.get("sub")
    email = (userinfo.get("email") or "").strip().lower()
    if not google_id or not email or not userinfo.get("email_verified"):
        return RedirectResponse(url=f"{LOGIN_PATH}?error=google_failed", status_code=303)

    display_name = _CONTROL_CHAR_PATTERN.sub(" ", userinfo.get("name") or "")
    display_name = " ".join(display_name.split())[:50]

    conn = await db.get_db()
    c = conn.cursor()
    try:
        try:
            user, event = await _resolve_or_create_google_user(c, google_id, email, display_name)
        except _GoogleAccountConflict:
            return RedirectResponse(url=f"{LOGIN_PATH}?error=google_failed", status_code=303)

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.db_execute(c, "UPDATE users SET last_login = ? WHERE id = ?", (ts, user["id"]))
        await conn.commit()
        start_session(request, user_id=user["id"], email=user["email"], session_version=user["session_version"] or 0, remember_me=True)
    finally:
        await conn.close()
    await record_event(event, request=request, user_id=user["id"], email=email)

    return RedirectResponse(url="/", status_code=303)


@router.get("/forgot_password")
async def forgot_password(request: Request):
    return RedirectResponse(url=LOGIN_PATH, status_code=303)


# POST only: a GET would let any page sign a visitor out with an <img> tag. The
# session version is bumped so a copied cookie stops working as well, not just
# this browser's copy.
@router.post("/auth/logout")
@router.post("/logout")
async def logout(request: Request):
    uid = get_user(request)
    if uid is not None:
        conn = await db.get_db()
        try:
            c = conn.cursor()
            await db.db_execute(c, "UPDATE users SET session_version = session_version + 1 WHERE id = ?", (uid,))
            await conn.commit()
        finally:
            await conn.close()
        await record_event("logout", request=request, user_id=uid)
    clear_login(request)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"success": True})
    return RedirectResponse(url=LOGIN_PATH, status_code=303)


# ---------------------------------------------------------------------------
# Profile — display name + password
# ---------------------------------------------------------------------------
@router.get("/me")
async def current_user(request: Request):
    """Session-identity check + current user info for non-Jinja frontends —
    used both as the Next.js port's "am I logged in" auth-wrapper check and
    as /profile's data source (the Jinja page gets the same data for free
    via tpl_context(); this is the only other consumer)."""
    uid = get_user(request)
    if uid is None:
        # lang is included even when logged out: /login and /register have no
        # session user but still need to render in the visitor's chosen language.
        return JSONResponse({"authenticated": False, "lang": get_lang(request)}, status_code=401)
    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "SELECT username, email FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    await conn.close()
    return JSONResponse(
        {
            "authenticated": True,
            "display_name": (user_row["username"] if user_row else None) or "",
            "email": user_row["email"] if user_row else "",
            # The Jinja pages read the session language straight off
            # tpl_context(); a non-Jinja frontend has no other way to learn
            # it, and it drives real behavior there (TTS voice, calendar
            # locale, which language button renders as active).
            "lang": get_lang(request),
        }
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url=LOGIN_PATH, status_code=303)
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

    if not await check_and_increment(f"pwchange:{uid}", PASSWORD_CHANGE_LIMIT, PASSWORD_CHANGE_WINDOW):
        return fail("Too many attempts. Please wait a few minutes." if lang == 'en' else "嘗試次數過多，請稍後再試", field="current_password", status_code=429)

    conn = await db.get_db()
    c = conn.cursor()
    await db.db_execute(c, "SELECT password FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    if (
        not user_row
        or len(current_password) > MAX_PASSWORD_LENGTH
        or not await verify_password_async(current_password, user_row["password"])
    ):
        await conn.close()
        return fail("Current password is incorrect" if lang == 'en' else "現時密碼不正確", field="current_password")

    new_password_error = _password_error(new_password, lang)
    if new_password_error:
        await conn.close()
        return fail(new_password_error, field="new_password")

    if new_password != confirm_new_password:
        await conn.close()
        return fail("Passwords do not match" if lang == 'en' else "密碼唔一致", field="confirm_new_password")

    # Every other signed-in browser must start over; this one stays signed in.
    await db.db_execute(
        c,
        "UPDATE users SET password = ?, session_version = session_version + 1 WHERE id = ? RETURNING session_version",
        (await hash_password_async(new_password), uid),
    )
    new_version = c.fetchone()["session_version"]
    await conn.commit()
    await conn.close()
    request.session["sv"] = new_version
    await record_event("password_change", request=request, user_id=uid)
    return JSONResponse({"success": True, "message": "Password updated" if lang == 'en' else "密碼已更新"})
