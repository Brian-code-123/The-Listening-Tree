"""
run.py — Main application server for The Listening Tree.

An elderly-focused AI companion chatbot built with FastAPI.
Provides bilingual chat (EN / zh-HK), voice interaction,
reminder management, memory games, calendar with HK public
holidays, and a local news feed.

Stack:
    - FastAPI 0.128+  (async ASGI web framework)
    - Uvicorn 0.35+   (high-performance ASGI server)
    - Tencent Hunyuan  (LLM chat API, hunyuan-pro)
    - SQLite3          (lightweight embedded database)
    - Vosk 0.3.45      (offline English STT, optional)
    - Web Speech API   (browser-side STT/TTS for EN + zh-HK)

Author:  The Listening Tree Team
License: Academic — Educational & Research Use
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
import io
import json
import wave
import base64
import secrets
import random
import threading
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import httpx
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from translations import get_text, get_all_translations, TRANSLATIONS

# ---------------------------------------------------------------------------
# Application initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="The Listening Tree",
    description="Bilingual AI companion chatbot for elderly wellness",
    version="2.0.0",
)
# Session secret: prefer explicit environment variable for production stability.
# If not provided, fall back to a generated ephemeral key (NOT recommended).
_SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("FLASK_SECRET") or secrets.token_hex(16)
if _SECRET_KEY and len(_SECRET_KEY) >= 16:
    print("[SECURITY] 🔑 SECRET_KEY is set")
else:
    print("[SECURITY] ⚠ No SECRET_KEY/FLASK_SECRET set — using ephemeral key")
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Vosk STT — lazy-loaded on first use (English offline model)
#
# Vosk provides fully offline speech-to-text for English.
# On Vercel (serverless), the native binary is unavailable so voice
# recognition falls back to the browser's Web Speech API exclusively.
# ---------------------------------------------------------------------------
_vosk_model = None
_vosk_lock = threading.Lock()
VOSK_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "voice_models", "vosk-model-small-en-us-0.15"
)

# Detect Vercel environment (serverless — no persistent filesystem)
ON_VERCEL = bool(os.environ.get("VERCEL"))


def get_vosk_model():
    """Return the cached Vosk Model instance (thread-safe, singleton).

    Returns None when running on Vercel or if the model directory is
    missing.  The first call that finds a valid model directory will
    load the model and cache it for all subsequent requests.
    """
    global _vosk_model
    if ON_VERCEL:
        return None
    if _vosk_model is not None:
        return _vosk_model
    with _vosk_lock:
        if _vosk_model is None:
            if os.path.isdir(VOSK_MODEL_PATH):
                try:
                    from vosk import Model
                    _vosk_model = Model(VOSK_MODEL_PATH)
                    print("[Vosk] ✅ English STT model loaded")
                except Exception as e:
                    print(f"[Vosk] ⚠ Failed to load model: {e}")
            else:
                print(f"[Vosk] ⚠ Model not found at {VOSK_MODEL_PATH}")
    return _vosk_model

# ---------------------------------------------------------------------------
# In-memory state  (lost on server restart — by design)
# ---------------------------------------------------------------------------
# Per-user quiz progress: { user_id: { is_game_mode, current_index, ... } }
user_game_states: dict = {}

# Per-(user, lang) conversation context sent to the LLM
user_api_histories: dict = {}

# Messages older than this are soft-deleted from chat_history
CHAT_HISTORY_RETENTION_MINUTES = 30

# ---------------------------------------------------------------------------
# AI configuration — Tencent Hunyuan (腾讯混元大模型)
# ---------------------------------------------------------------------------
AI_API_KEY = os.environ.get("HUNYUAN_API_KEY")
AI_BASE_URL = os.environ.get("HUNYUAN_BASE_URL", "https://api.hunyuan.cloud.tencent.com/v1")
AI_MODEL = os.environ.get("HUNYUAN_MODEL", "hunyuan-pro")

if AI_API_KEY:
    print(f"[AI] ✅ {AI_MODEL} configured (Tencent Hunyuan 腾讯混元)")
else:
    print("[AI] ⚠ HUNYUAN_API_KEY not set — using warm fallback responses")

print("[STT] ✅ Browser Web Speech API ready (EN + zh-HK, zero server deps)")

# System prompt — Cantonese elderly companion (Chinese)
# Guides the LLM to reply in warm, patient Cantonese with simple vocabulary.
WARM_SYSTEM_PROMPT_ZH = """你係一個非常溫暖、親切、有耐心嘅陪伴者，專門陪老人家傾偈，稱呼對方做朋友。

你嘅講嘢風格：
- 你一定要用廣東話（粵語）回答，唔好用普通話！
- 語氣溫柔、充滿關懷，好似孫仔女咁同老人家傾偈
- 講嘢簡單易明，唔用複雜詞語
- 成日表達關心：「你今日點呀？」「食咗飯未？」「有冇瞓得好？」
- 多用正面鼓勵嘅說話
- 如果老人家講唔清楚或重複問題，要非常有耐心，唔好顯出唔耐煩
- 多用「好呀」、「真係好」、「你真係叻」等鼓勵說話
- 偶爾分享溫馨小故事或回憶往事
- 回覆保持簡短（2-4句），易讀易明

重要：直接回答用戶嘅問題，唔好顯示你嘅思考過程或分析步驟。
重要：你一定要用廣東話回答，唔好用普通話或者書面語。

記住：你嘅目標係令老人家覺得溫暖、被關心、唔孤單。"""

# System prompt — English elderly companion
# Guides the LLM to reply in warm, patient English with simple vocabulary.
WARM_SYSTEM_PROMPT_EN = """You are a very warm, kind, and patient companion who chats with elderly people.

Your speaking style:
- Gentle and caring tone, like a grandchild talking with their grandparent
- Use simple, easy-to-understand language
- Frequently express concern: "How are you today?" "Have you eaten?" "Did you sleep well?"
- Use positive encouragement and uplifting words
- Be very patient if the user is unclear or repeats questions — never show impatience
- Use phrases like "That's wonderful!", "I'm so glad to hear that!", "You're doing great!"
- Occasionally share warm stories or reminisce about good times
- Keep responses short (2-4 sentences), easy to read and understand

IMPORTANT: Answer the user's questions directly without showing your reasoning process or analysis steps.

Remember: Your goal is to make elderly people feel warm, cared for, and less lonely."""

# Warm fallback responses — returned when the LLM API key is missing or
# the API call fails.  Keeps the UX friendly even under degraded mode.
WARM_FALLBACK_ZH = [
    "你好呀！好開心見到你。你今日過得點呀？😊",
    "唔好擔心，有咩事都可以同我講。我會一直陪住你㗎！",
    "你講嘅嘢我都有聽到，我覺得你真係好叻呀！",
    "好呀好呀，繼續同我傾偈啦！我最鍾意聽你講嘢。",
    "你真係好叻！記得要照顧自己身體呀，食多啲好嘢。😊",
    "多謝你同我分享，你嘅故事真係好有趣！繼續講啦！",
    "我明白你嘅感受。記住，你唔係一個人，我會一直陪住你。",
    "哈哈，你講嘅嘢真係好得意！你成日都咁開心就好喇。",
    "今日天氣點呀？記得著多件衫，唔好凍親呀！",
    "你有冇瞓得好呀？早啲瞓覺對身體好㗎。",
]

WARM_FALLBACK_EN = [
    "That's really interesting! Tell me more about that, I'd love to hear. 😊",
    "I understand what you mean. How does that make you feel?",
    "Thank you for sharing that with me. I really enjoy our conversations.",
    "That sounds lovely! What else have you been up to today?",
    "I appreciate you telling me about that. Is there anything else on your mind?",
    "It's always so nice chatting with you. What else would you like to talk about?",
    "I hear you, and I think that's wonderful. Tell me more! 😊",
]

async def call_ai(user_input: str, user_id: int, lang: str = 'en'):
    """Call Tencent Hunyuan API for warm elderly conversation."""
    system_prompt = WARM_SYSTEM_PROMPT_ZH if lang == 'zh-HK' else WARM_SYSTEM_PROMPT_EN
    fallback = WARM_FALLBACK_ZH if lang == 'zh-HK' else WARM_FALLBACK_EN

    if not AI_API_KEY:
        return random.choice(fallback)

    history_key = (user_id, lang)
    if history_key not in user_api_histories:
        user_api_histories[history_key] = []
    history = user_api_histories[history_key]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-20:])
    messages.append({"role": "user", "content": user_input})

    body = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.8,
        "top_p": 0.9,
        "max_tokens": 512,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            result = resp.json()

        message = result["choices"][0]["message"]
        reply = message.get("content") or ""

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})
        if len(history) > 30:
            user_api_histories[history_key] = history[-20:]

        return reply

    except Exception as e:
        print(f"[AI] API error ({lang}): {e}")
        return random.choice(fallback)

# ---------------------------------------------------------------------------
# Quiz / Memory-game questions  (cognitive engagement feature)
#
# Answers are compared case-insensitively.  Keep answers as lowercase
# strings so the comparison in the game loop stays simple.
# ---------------------------------------------------------------------------

# Cantonese quiz questions
questions_zh = [
    {"question": "法國嘅首都係邊度？", "answer": "巴黎"},
    {"question": "2 + 2 等於幾多？", "answer": "4"},
    {"question": "晴天嘅天空係咩顏色？", "answer": "藍色"},
    {"question": "有一種水果，外面紅色，入面白色，有好多黑色嘅籽。係咩嚟㗎？", "answer": "西瓜"},
    {"question": "邊個月份有28日？", "answer": "每個月都有至少28日"},
    {"question": "水嘅化學符號係咩？", "answer": "h2o"},
]

# English quiz questions
questions = [
    {"question": "What's the capital of France?", "answer": "paris"},
    {"question": "What's 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"},
    {"question": "There is a fruit with a red outer skin and white inside with small black seeds. What is it?", "answer": "watermelon"},
    {"question": "Which month has 28 days?", "answer": "every month has at least 28 days"},
    {"question": "What is the chemical symbol for water?", "answer": "h2o"}
]

# ---------------------------------------------------------------------------
# Database Setup — SQLite3
#
# On Vercel the project filesystem is read-only so we write to /tmp.
# For production persistence swap to an external DB (Turso / Neon / Supabase).
# ---------------------------------------------------------------------------
_DB_PATH = os.environ.get(
    "DATABASE_URL",
    "/tmp/reminders.db" if ON_VERCEL else "reminders.db",
)


def get_db() -> sqlite3.Connection:
    """Open a new SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        reminder_time TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        repeat_type TEXT DEFAULT 'once',
        priority TEXT DEFAULT 'normal',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lang TEXT DEFAULT 'en',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_bot BOOLEAN NOT NULL,
        message TEXT NOT NULL,
        is_deleted BOOLEAN DEFAULT 0,
        token_count INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pref_key TEXT NOT NULL,
        pref_value TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(user_id, pref_key)
    )""")

    c.execute('CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, is_active)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_deleted ON chat_history(user_id, is_deleted)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pref_user ON preferences(user_id, pref_key)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(user_id, created_at)')

    # Migration: add lang column if missing (must run before lang index)
    try:
        c.execute("SELECT lang FROM chat_history LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE chat_history ADD COLUMN lang TEXT DEFAULT 'en'")

    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_lang ON chat_history(user_id, lang)')
    conn.commit()
    conn.close()
    print("[DB] ✅ Database initialized")


# Run once at import time to ensure tables exist
init_db()


# ---------------------------------------------------------------------------
# Background helpers — housekeeping tasks
# ---------------------------------------------------------------------------

def cleanup_old_chat_history() -> None:
    """Soft-delete chat messages older than *CHAT_HISTORY_RETENTION_MINUTES*.

    Sets ``is_deleted = 1`` instead of physically removing rows so that
    analytics or audit queries can still access the data if needed.
    """
    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()
    cutoff_time = datetime.now().timestamp() - (CHAT_HISTORY_RETENTION_MINUTES * 60)
    cutoff_datetime = datetime.fromtimestamp(cutoff_time).strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "UPDATE chat_history SET is_deleted = 1 WHERE timestamp < ? AND is_deleted = 0",
        (cutoff_datetime,),
    )
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    if deleted_count > 0:
        print(f"[CLEANUP] 🗑️  Marked {deleted_count} old messages as deleted")


def auto_expire_old_reminders() -> None:
    """Deactivate reminders created before today.

    Runs once per hour (top of the hour) from the background thread.
    """
    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "UPDATE reminders SET is_active = 0, updated_at = ? "
        "WHERE DATE(created_at) < ? AND is_active = 1",
        (ts, today),
    )
    expired = c.rowcount
    conn.commit()
    conn.close()
    if expired > 0:
        print(f"[EXPIRE] 📅 Marked {expired} old reminders as inactive")


def check_reminders() -> None:
    """Background loop (daemon thread): check reminders every 60 s.

    Also triggers periodic housekeeping:
      - auto_expire_old_reminders   every hour (minute == 0)
      - cleanup_old_chat_history    every 10 minutes
    """
    while True:
        conn = sqlite3.connect(_DB_PATH)
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M")
        c.execute(
            "SELECT u.email, r.label, r.reminder_time FROM reminders r "
            "JOIN users u ON r.user_id = u.id "
            "WHERE r.is_active = 1 AND DATE(r.created_at) = ?",
            (today,),
        )
        for email, label, rtime in c.fetchall():
            if rtime == current_time:
                print(f"[REMINDER] ⏰ {email}: {label} at {rtime}")
        conn.close()

        # Periodic housekeeping
        if datetime.now().minute == 0:
            auto_expire_old_reminders()
        if datetime.now().minute % 10 == 0:
            cleanup_old_chat_history()

        threading.Event().wait(60)


# Start background reminder thread (skip on Vercel — serverless has no
# persistent threads)
if not ON_VERCEL:
    threading.Thread(target=check_reminders, daemon=True).start()
else:
    print("[INFO] Vercel mode — background reminder thread disabled")

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_user(request: Request) -> int | None:
    """Return the logged-in user's DB id, or *None* if unauthenticated."""
    return request.session.get("user_id")


def get_lang(request: Request) -> str:
    """Return the current UI language code ('en' or 'zh-HK')."""
    return request.session.get("language", "en")


def require_login(request: Request) -> int:
    """Return user id or redirect to /login via 303 See Other."""
    uid = get_user(request)
    if uid is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return uid


# ---------------------------------------------------------------------------
# Template context builder
# ---------------------------------------------------------------------------

def tpl_context(request: Request, **kwargs) -> dict:
    """Build a Jinja2 template context with common variables.

    Every template receives *request*, *lang*, and *translations* automatically.
    Extra keyword arguments are merged in.
    """
    lang = get_lang(request)
    ctx = {
        "request": request,
        "lang": lang,
        "translations": get_all_translations(lang),
    }
    ctx.update(kwargs)
    return ctx

# ---------------------------------------------------------------------------
# Auth Routes — login / register / logout
# ---------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    lang = get_lang(request)
    return templates.TemplateResponse("login.html", tpl_context(request))

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    """Authenticate user login with email and password credentials.

    Sets session values on successful authentication:
      - session['user_id']: Database row ID
      - session['user_email']: User email address
      - session['language']: User's preferred language (loaded from preferences table)

    Args:
        request: HTTP request object with session middleware
        email: User email (case-sensitive, must match registered email exactly)
        password: Plain-text password (compared directly; not hashed)

    Returns:
        HTMLResponse: Redirect to / (home) on success, or login.html with error message on failure
    """
    lang = get_lang(request)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, email FROM users WHERE email = ? AND password = ?", (email, password))
    user = c.fetchone()
    if user:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("UPDATE users SET last_login = ? WHERE id = ?", (ts, user["id"]))
        conn.commit()
        request.session['user_email'] = user["email"]
        request.session['user_id'] = user["id"]
        # Load language preference
        c.execute("SELECT pref_value FROM preferences WHERE user_id = ? AND pref_key = 'language'", (user["id"],))
        pref = c.fetchone()
        if pref:
            request.session['language'] = pref["pref_value"]
        conn.close()
        return RedirectResponse(url="/", status_code=303)
    conn.close()
    return templates.TemplateResponse("login.html", tpl_context(request, error="Invalid email or password" if lang == 'en' else "電郵或密碼錯誤"))

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", tpl_context(request))

@app.post("/register", response_class=HTMLResponse)
async def register_post(request: Request, email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    """Create a new user account (registration).

    Validation steps:
      1. Confirm password == password (client-side + server-side check)
      2. Email must be unique (SQLite UNIQUE constraint)
      3. Password stored in plaintext (NOT production-safe; use bcrypt/Argon2 for real apps)

    On success: Inserts new user row with created_at timestamp, redirects to /login.
    On failure: Returns register.html with localized error message.

    Args:
        request: HTTP request object
        email: Email address (must not exist in users table)
        password: Password in plaintext
        confirm_password: Confirmation password (must == password)

    Returns:
        HTMLResponse: Redirect to /login on success, or register.html with error on failure
    """
    lang = get_lang(request)
    if password != confirm_password:
        return templates.TemplateResponse("register.html", tpl_context(request, error="Passwords do not match" if lang == 'en' else "密碼唔一致"))
    conn = get_db()
    c = conn.cursor()
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)", (email, password, ts))
        conn.commit()
        conn.close()
        return RedirectResponse(url="/login", status_code=303)
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("register.html", tpl_context(request, error="Email already exists" if lang == 'en' else "電郵已存在"))

@app.get("/forgot_password")
async def forgot_password(request: Request):
    return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

# ---------------------------------------------------------------------------
# Main Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("chat.html", tpl_context(request))

@app.get("/set_language/{lang}")
async def set_language(request: Request, lang: str):
    if lang in ('en', 'zh-HK'):
        request.session['language'] = lang
        uid = get_user(request)
        if uid:
            conn = get_db()
            c = conn.cursor()
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("INSERT OR REPLACE INTO preferences (user_id, pref_key, pref_value, updated_at) VALUES (?, ?, ?, ?)",
                      (uid, 'language', lang, ts))
            conn.commit()
            conn.close()
    referer = request.headers.get('referer', '/')
    return RedirectResponse(url=referer, status_code=303)

@app.get("/accessibility", response_class=HTMLResponse)
async def accessibility_mode(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("accessibility.html", tpl_context(request))

# ---------------------------------------------------------------------------
# Chat Response — the core message handler
#
# Accepts free-text input from the user, checks for special command
# prefixes (reminders, games, preferences), and falls through to the
# Tencent Hunyuan LLM for general conversation.
# ---------------------------------------------------------------------------
@app.post("/get_response")
async def get_response(request: Request, msg: str = Form(...)):
    """Process user message and return AI/command response.

    Message handling priority (in order):
      1. Guide trigger keywords ('teach', 'how to use', 'help') → return help text
      2. Reminder commands ('set reminder', 'delete reminder') → parse, validate, store in DB
      3. Preference commands ('set preference') → update preferences table
      4. Game commands ('play game', 'exit game', quiz answers) → manage game state in memory
      5. Default → send to Tencent Hunyuan LLM for warm conversation response

    Chat history: Every user message + bot response is logged to chat_history table with:
      - user_id: Current session user ID
      - lang: Current UI language (en or zh-HK)
      - timestamp: ISO timestamp
      - is_bot: 0 for user, 1 for bot
      - message: Text content

    Args:
        request: HTTP request (must have user_id in session)
        msg: User input text (may be voice-transcribed)

    Returns:
        JSONResponse: {"response": str} with bot reply or error
    """
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"response": "Please log in."}, status_code=401)

    lang = get_lang(request)
    user_input_original = msg.strip()
    user_input_lower = user_input_original.lower()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    c = conn.cursor()

    # Store user message with language tag
    c.execute("INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted) VALUES (?, ?, ?, 0, ?, 0)",
              (uid, lang, timestamp, user_input_original))
    conn.commit()

    response = ""

    # ---- Check for guide-helper trigger keywords ----
    guide_triggers_zh = ['教', '點用', '唔明', '幫教']
    guide_triggers_en = ['teach', 'how to use', 'help me', 'guide']
    is_guide_trigger = False
    if lang == 'zh-HK':
        is_guide_trigger = any(t in user_input_original for t in guide_triggers_zh)
    else:
        is_guide_trigger = any(t in user_input_lower for t in guide_triggers_en)

    if is_guide_trigger:
        if lang == 'zh-HK':
            response = ("📖 你可以撳右下角嘅「？」按鈕打開操作指引！入面有所有功能嘅使用方法。\n\n"
                        "簡單指令：\n"
                        "• 打字或者講嘢同我傾偈\n"
                        "• 「設置提醒 食藥 09:00」設提醒\n"
                        "• 「玩遊戲」開始問答遊戲\n"
                        "• 撳🔍按鈕搜尋網頁\n"
                        "• 撳📎按鈕上傳檔案")
        else:
            response = ("📖 Click the '?' button at the bottom-right to open the Operation Guide!\n\n"
                        "Quick commands:\n"
                        "• Type or speak to chat with me\n"
                        "• 'set reminder take medicine 09:00' to set a reminder\n"
                        "• 'play game' to start a quiz\n"
                        "• Click 🔍 button for web search\n"
                        "• Click 📎 button to upload files")

    # ---- Reminder Commands ----
    elif user_input_lower.startswith("set reminder") or user_input_lower.startswith("設置提醒"):
        if user_input_lower.startswith("設置提醒"):
            parts = user_input_original.split()
            if len(parts) >= 3 and ':' in parts[-1]:
                time_str = parts[-1]
                label = ' '.join(parts[1:-1])
            else:
                response = "格式：設置提醒 [活動] [HH:MM]"
                c.execute("INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted) VALUES (?, ?, ?, 1, ?, 0)", (uid, lang, timestamp, response))
                conn.commit(); conn.close()
                return JSONResponse({"response": response})
        else:
            parts = user_input_lower.split()
            if len(parts) >= 4 and len(parts[-1]) == 5 and parts[-1][2] == ':':
                time_str = parts[-1]
                label = ' '.join(parts[2:-1])
            else:
                response = "Usage: set reminder [activity] [HH:MM]"
                c.execute("INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted) VALUES (?, ?, ?, 1, ?, 0)", (uid, lang, timestamp, response))
                conn.commit(); conn.close()
                return JSONResponse({"response": response})

        try:
            h, m = map(int, time_str.split(':'))
            if 0 <= h <= 23 and 0 <= m <= 59:
                c.execute("INSERT INTO reminders (user_id, label, reminder_time, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                          (uid, label, time_str, timestamp))
                conn.commit()
                response = f"提醒已設置：{label}，時間 {time_str}" if lang == 'zh-HK' else f"Reminder set: {label} at {time_str}"
            else:
                response = "時間無效。請用24小時格式 HH:MM" if lang == 'zh-HK' else "Invalid time. Use 24-hour format HH:MM"
        except:
            response = "時間格式錯誤。請用 HH:MM" if lang == 'zh-HK' else "Invalid time format. Use HH:MM"

    elif user_input_lower.startswith("delete reminder") or user_input_lower.startswith("刪除提醒"):
        if user_input_lower.startswith("刪除提醒"):
            parts = user_input_original.split(maxsplit=1)
            label = parts[1] if len(parts) == 2 else None
        else:
            parts = user_input_lower.split(maxsplit=2)
            label = parts[2] if len(parts) == 3 else None
        if label:
            c.execute("DELETE FROM reminders WHERE user_id = ? AND label = ?", (uid, label))
            if c.rowcount > 0:
                response = f"已刪除提醒：{label}" if lang == 'zh-HK' else f"Deleted reminder: {label}"
            else:
                response = "搵唔到呢個提醒。" if lang == 'zh-HK' else "No reminder found with that name."
            conn.commit()
        else:
            response = "格式：刪除提醒 [活動]" if lang == 'zh-HK' else "Usage: delete reminder [activity]"

    # ---- Preference Commands ----
    elif user_input_lower.startswith("set preference"):
        parts = user_input_lower.split(maxsplit=4)
        if len(parts) >= 4:
            key, value = parts[2], parts[3]
            c.execute("INSERT OR REPLACE INTO preferences (user_id, pref_key, pref_value, updated_at) VALUES (?, ?, ?, ?)",
                      (uid, key, value, timestamp))
            conn.commit()
            response = f"Preference updated: {key} = {value}"
        else:
            response = "Usage: set preference [key] [value]"

    # ---- Quiz Game ----
    else:
        active_questions = questions_zh if lang == 'zh-HK' else questions
        game = user_game_states.setdefault(uid, {
            'is_game_mode': False, 'current_index': 0,
            'current_question': None, 'correct_answer': None, 'score': 0
        })
        game_trigger = user_input_lower in ["play game", "玩遊戲", "玩游戏"]
        exit_trigger = user_input_lower in ["exit game", "退出遊戲", "退出游戏"]

        if game_trigger and not game['is_game_mode']:
            game['is_game_mode'] = True
            game['current_index'] = 0
            game['score'] = 0
            q = active_questions[0]
            game['current_question'] = q["question"]
            game['correct_answer'] = q["answer"]
            if lang == 'zh-HK':
                response = f"開始玩喇！一共有{len(active_questions)}條問題。分數：0。第一條問題：{game['current_question']}"
            else:
                response = f"Let's play! You have {len(active_questions)} questions. Current score: 0. First question: {game['current_question']}"

        elif exit_trigger and game['is_game_mode']:
            game['is_game_mode'] = False
            if lang == 'zh-HK':
                response = f"遊戲結束！你答啱咗{game['score']}條（總共{game['current_index']}條）。"
            else:
                response = f"Game stopped. You got {game['score']} out of {game['current_index']} correct so far!"

        elif game['is_game_mode']:
            if user_input_lower.strip() == game['correct_answer']:
                game['score'] += 1
                response = f"啱咗！分數：{game['score']}" if lang == 'zh-HK' else f"Correct! Score: {game['score']}"
            else:
                if lang == 'zh-HK':
                    response = f"唔啱呀，答案係{game['correct_answer']}。分數：{game['score']}"
                else:
                    response = f"Incorrect. The answer was {game['correct_answer']}. Score: {game['score']}"
            game['current_index'] += 1
            if game['current_index'] == len(active_questions):
                if lang == 'zh-HK':
                    response += f"\n遊戲完成！你答啱咗{game['score']}條（總共{len(active_questions)}條）。叻叻！"
                else:
                    response += f"\nGame over! You successfully answered {game['score']} out of {len(active_questions)} questions correctly."
                game['is_game_mode'] = False
            else:
                q = active_questions[game['current_index']]
                game['current_question'] = q["question"]
                game['correct_answer'] = q["answer"]
                if lang == 'zh-HK':
                    response += f" 下一條問題：{q['question']}"
                else:
                    response += f" Next question: {q['question']}"

        # ---- Normal AI Chat ----
        else:
            response = await call_ai(user_input_original, uid, lang)

    # Store bot response
    c.execute("INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted) VALUES (?, ?, ?, 1, ?, 0)",
              (uid, lang, timestamp, response))
    conn.commit()
    conn.close()

    return JSONResponse({"response": response})

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Voice Transcription — Vosk offline English STT
#
# The browser captures a mono 16 kHz PCM WAV blob and POSTs it here.
# For Cantonese the client-side Web Speech API is used exclusively.
# ---------------------------------------------------------------------------
@app.post("/transcribe")
async def transcribe_audio(request: Request, audio: UploadFile = File(...)):
    """Receive raw 16 kHz mono PCM WAV from browser, return transcribed text."""
    model = get_vosk_model()
    if model is None:
        return JSONResponse({"text": "", "error": "STT model not available"})

    audio_bytes = await audio.read()
    try:
        from vosk import KaldiRecognizer
        import wave, io

        # Parse the WAV the browser sent
        with wave.open(io.BytesIO(audio_bytes)) as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                return JSONResponse({"text": "", "error": "Expected mono 16-bit WAV"})
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        rec = KaldiRecognizer(model, sample_rate)
        rec.SetWords(False)

        CHUNK = 4000
        for i in range(0, len(frames), CHUNK):
            rec.AcceptWaveform(frames[i:i + CHUNK])

        result = json.loads(rec.FinalResult())
        text = result.get("text", "").strip()
        return JSONResponse({"text": text})
    except Exception as e:
        print(f"[Vosk] Transcription error: {e}")
        return JSONResponse({"text": "", "error": str(e)})

# ---------------------------------------------------------------------------
# Reminder Management endpoints (AJAX)
# ---------------------------------------------------------------------------
@app.post("/deactivate_reminder")
async def deactivate_reminder(request: Request, label: str = Form(...)):
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"success": False}, status_code=401)
    conn = get_db()
    c = conn.cursor()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE reminders SET is_active = 0, updated_at = ? WHERE user_id = ? AND label = ?", (ts, uid, label))
    conn.commit()
    conn.close()
    return JSONResponse({"success": True})

@app.get("/get_reminders")
async def get_reminders(request: Request):
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"reminders": []})
    conn = get_db()
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT label, reminder_time, is_active FROM reminders WHERE user_id = ? AND DATE(created_at) = ? ORDER BY created_at DESC",
              (uid, today))
    reminders = [{"label": r["label"], "time": r["reminder_time"], "active": bool(r["is_active"])} for r in c.fetchall()]
    conn.close()
    return JSONResponse({"reminders": reminders})

@app.get("/get_chat_history")
async def get_chat_history(request: Request):
    """Get chat history for current user, filtered by current language."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"history": []})
    lang = get_lang(request)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT timestamp, is_bot, message FROM chat_history WHERE user_id = ? AND lang = ? AND is_deleted = 0 ORDER BY timestamp",
              (uid, lang))
    history = [{"timestamp": r["timestamp"], "sender": "bot" if r["is_bot"] else "user", "message": r["message"]} for r in c.fetchall()]
    conn.close()
    return JSONResponse({"history": history})

# ---------------------------------------------------------------------------
# HK Public Holidays 2025-2027
#
# Static dataset consumed by FullCalendar on the client side.
# ---------------------------------------------------------------------------
HK_HOLIDAYS = [
    # 2025
    {"date": "2025-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2025-01-29", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2025-01-30", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2025-01-31", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2025-04-04", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2025-04-18", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2025-04-19", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2025-04-21", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2025-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2025-05-05", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2025-05-31", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2025-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2025-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2025-10-07", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2025-10-29", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2025-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2025-12-26", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
    # 2026
    {"date": "2026-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2026-02-17", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2026-02-18", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2026-02-19", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2026-04-03", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2026-04-04", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2026-04-05", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2026-04-06", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2026-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2026-05-24", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2026-06-19", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2026-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2026-09-26", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2026-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2026-10-17", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2026-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2026-12-26", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
    # 2027
    {"date": "2027-01-01", "name_en": "New Year's Day", "name_zh": "元旦"},
    {"date": "2027-02-06", "name_en": "Lunar New Year's Day", "name_zh": "農曆年初一"},
    {"date": "2027-02-07", "name_en": "Second day of Lunar New Year", "name_zh": "農曆年初二"},
    {"date": "2027-02-08", "name_en": "Third day of Lunar New Year", "name_zh": "農曆年初三"},
    {"date": "2027-03-26", "name_en": "Good Friday", "name_zh": "耶穌受難節"},
    {"date": "2027-03-27", "name_en": "Day after Good Friday", "name_zh": "耶穌受難節翌日"},
    {"date": "2027-03-29", "name_en": "Easter Monday", "name_zh": "復活節星期一"},
    {"date": "2027-04-05", "name_en": "Ching Ming Festival", "name_zh": "清明節"},
    {"date": "2027-05-01", "name_en": "Labour Day", "name_zh": "勞動節"},
    {"date": "2027-05-13", "name_en": "Buddha's Birthday", "name_zh": "佛誕"},
    {"date": "2027-06-09", "name_en": "Tuen Ng Festival", "name_zh": "端午節"},
    {"date": "2027-07-01", "name_en": "HKSAR Establishment Day", "name_zh": "香港特別行政區成立紀念日"},
    {"date": "2027-09-16", "name_en": "Day after Mid-Autumn Festival", "name_zh": "中秋節翌日"},
    {"date": "2027-10-01", "name_en": "National Day", "name_zh": "國慶日"},
    {"date": "2027-10-08", "name_en": "Chung Yeung Festival", "name_zh": "重陽節"},
    {"date": "2027-12-25", "name_en": "Christmas Day", "name_zh": "聖誕節"},
    {"date": "2027-12-27", "name_en": "Day after Christmas", "name_zh": "聖誕節後第一個周日"},
]

@app.get("/get_hk_holidays")
async def get_hk_holidays(request: Request):
    """Return HK public holidays for FullCalendar."""
    lang = get_lang(request)
    events = []
    for h in HK_HOLIDAYS:
        events.append({
            "title": h["name_zh"] if lang == "zh-HK" else h["name_en"],
            "start": h["date"],
            "allDay": True,
            "color": "#E07A5F",
            "textColor": "#FFFFFF",
            "classNames": ["holiday-event"],
        })
    return JSONResponse({"holidays": events})

# ---------------------------------------------------------------------------
# HK News — proxy endpoint (NewsAPI with in-memory cache)
#
# Falls back to hardcoded placeholder articles when no API key is set.
# Cache TTL: 30 minutes.
# ---------------------------------------------------------------------------
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '')
_news_cache = {"data": None, "timestamp": 0, "lang": None}

async def fetch_hk_news(lang: str = 'en'):
    """Fetch HK news from NewsAPI; cache for 30 min."""
    import time
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["timestamp"]) < 1800 and _news_cache["lang"] == lang:
        return _news_cache["data"]

    articles = []

    # Try NewsAPI if key available
    if NEWS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params={"country": "hk", "pageSize": 8, "apiKey": NEWS_API_KEY}
                )
                resp.raise_for_status()
                data = resp.json()
                for a in data.get("articles", [])[:8]:
                    articles.append({
                        "title": a.get("title", ""),
                        "description": a.get("description", "") or "",
                        "url": a.get("url", "#"),
                        "source": a.get("source", {}).get("name", ""),
                        "publishedAt": a.get("publishedAt", ""),
                        "image": a.get("urlToImage", ""),
                    })
        except Exception as e:
            print(f"[News] NewsAPI error: {e}")

    # Fallback: use hardcoded recent HK news placeholders
    if not articles:
        if lang == 'zh-HK':
            articles = [
                {"title": "天文台預測未來數日天氣回暖", "description": "天文台表示，受暖濕氣流影響，未來數日氣溫將回升至22-25度，市民外出請注意添減衣物。", "url": "#", "source": "天文台", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "港鐵新線路規劃公佈", "description": "政府今日公佈港鐵新線路規劃詳情，包括北環線及其延伸段，預計2030年完工通車。", "url": "#", "source": "政府新聞處", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "長者醫療券使用範圍擴大", "description": "政府宣佈長者醫療券使用範圍將進一步擴大，涵蓋更多醫療服務項目，惠及更多長者。", "url": "#", "source": "衛生署", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "沙田區社區活動日即將舉行", "description": "沙田區議會將於下週末舉辦社區活動日，設有健康檢查、興趣班及長者關懷活動。", "url": "#", "source": "區議會", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "本港今日天氣晴朗乾燥", "description": "天文台錄得今日最高氣溫23度，天氣晴朗乾燥，適合戶外活動。", "url": "#", "source": "天文台", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
            ]
        else:
            articles = [
                {"title": "HK Observatory forecasts warmer weather ahead", "description": "The Observatory expects temperatures to rise to 22-25°C over the next few days due to warm moist airflow.", "url": "#", "source": "HK Observatory", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "MTR new rail line planning announced", "description": "The government today released details of new MTR rail line planning, including the Northern Link and extensions, expected to be completed by 2030.", "url": "#", "source": "GovHK", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Elderly healthcare voucher scope expanded", "description": "The government announced an expansion of the elderly healthcare voucher scheme to cover more medical services.", "url": "#", "source": "Dept of Health", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Sha Tin community event day coming up", "description": "The Sha Tin District Council will host a community event day next weekend featuring health checks and elderly care activities.", "url": "#", "source": "District Council", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
                {"title": "Fine and dry weather in Hong Kong today", "description": "The Observatory recorded a high of 23°C today. Fine and dry weather, suitable for outdoor activities.", "url": "#", "source": "HK Observatory", "publishedAt": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "image": ""},
            ]

    _news_cache["data"] = articles
    _news_cache["timestamp"] = now
    _news_cache["lang"] = lang
    return articles

@app.get("/get_news")
async def get_news(request: Request):
    """Return HK local news articles."""
    lang = get_lang(request)
    articles = await fetch_hk_news(lang)
    return JSONResponse({"articles": articles})

# ---------------------------------------------------------------------------
# Development server entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("  The Listening Tree — Elderly Companion Chatbot")
    print("=" * 70)
    print(f"  AI Model       : {AI_MODEL} (Tencent Hunyuan)")
    print(f"  Chat retention  : {CHAT_HISTORY_RETENTION_MINUTES} min")
    print(f"  Voice (EN+zh-HK): Browser Web Speech API")
    print(f"  Features        : Reminders · Memory Games · HK Holidays · News")
    print("=" * 70)

    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)