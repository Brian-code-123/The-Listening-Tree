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
import asyncio
import secrets
import random
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, BackgroundTasks
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
# Minimal startup output
# By default we suppress module-level print() calls so running the server
# doesn't flood the console. Set MINIMAL_STARTUP=0 in the environment to
# retain the verbose messages during development.
# ---------------------------------------------------------------------------
_MINIMAL_STARTUP = os.environ.get("MINIMAL_STARTUP", "1") != "0"
if _MINIMAL_STARTUP:
    import builtins as _builtins
    # keep original print available for later (we'll restore it in __main__)
    _builtins._original_print = _builtins.print
    def _silent_print(*args, **kwargs):
        return None
    _builtins.print = _silent_print

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from translations import get_text, get_all_translations, TRANSLATIONS

# ---------------------------------------------------------------------------
# Background Periodic Task Manager (Async Replacement for Daemon Thread)
# ---------------------------------------------------------------------------
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
            conn = sqlite3.connect(_DB_PATH)
            c = conn.cursor()
            c.execute(
                "SELECT u.email, r.label, r.reminder_time FROM reminders r "
                "JOIN users u ON r.user_id = u.id "
                "WHERE r.is_active = 1 AND DATE(r.created_at) = ?",
                (today,),
            )
            for email, label, rtime in c.fetchall():
                if rtime == current_time:
                    # In a real app, this would trigger a push notification or WebSocket msg
                    _builtins._original_print(f"[REMINDER] ⏰  {email}: {label} at {rtime}")
            conn.close()

            # 2. Daily Housekeeping (Auto-expire old reminders at 00:00)
            if now.hour == 0 and now.minute == 0:
                auto_expire_old_reminders()

            # 3. Clean Chat History (Every 10 minutes)
            if now.minute % 10 == 0:
                cleanup_old_chat_history()

        except Exception as e:
            _builtins._original_print(f"[ERROR] periodic_tasks: {e}")

        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background task
    # Start the periodic background task. `asyncio.create_all_tasks()` does
    # not exist — use `create_task` to schedule the coroutine.
    task = asyncio.create_task(run_periodic_tasks())
    yield
    # Shutdown: Clean up task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

# ---------------------------------------------------------------------------
# Application initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="The Listening Tree",
    description="Bilingual AI companion chatbot for elderly wellness",
    version="2.0.0",
    lifespan=lifespan
)
# Session secret: prefer explicit environment variable for production stability.
# If not provided, fall back to a generated ephemeral key (NOT recommended).
_SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("SESSION_SECRET") or os.environ.get("FASTAPI_SECRET") or secrets.token_hex(16)
if _SECRET_KEY and len(_SECRET_KEY) >= 16:
    print("[SECURITY] 🔑 SECRET_KEY is set")
else:
    print("[SECURITY] ⚠ No SECRET_KEY/SESSION_SECRET/FASTAPI_SECRET set — using ephemeral key")
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

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
# ---------------------------------------------------------------------------
# AI configuration — Zhipu AI (智谱AI)
# ---------------------------------------------------------------------------
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
ZHIPU_MODEL = os.environ.get("ZHIPU_MODEL", "glm-4-flash")

if ZHIPU_API_KEY:
    print(f"[AI] ✅ {ZHIPU_MODEL} configured (Zhipu AI)")
else:
    print("[AI] ⚠ ZHIPU_API_KEY not set — using warm fallback responses")

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
    "你好，很高興與你相遇。今天過得還好嗎？😊",
    "不必擔心，無論什麼心事，都可以慢慢說給我聽。",
    "你說的話我都認真聽著，你真的很優秀。",
    "好的，請繼續說吧，我很樂意聆聽。",
    "你真的很棒，記得好好照顧自己，吃得飽、睡得好。😊",
    "謝謝你願意與我分享，你的故事很動人。",
    "我明白你的心情，請記住，你從來都不是一個人。",
    "聽你這麼說，真讓人開心，願你天天都有好心情。",
    "今天天氣如何？記得注意保暖，照顧好自己。",
    "昨晚睡得安穩嗎？好好休息，身體才會健康。",
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

async def call_ai(user_input: str, user_id: int, lang: str = 'en', image_data: Optional[str] = None):
    """Call Zhipu AI (智谱AI) for warm elderly conversation.
    Supports image-based "Photo Memories" with GLM-4v (Vision).
    """
    system_prompt = WARM_SYSTEM_PROMPT_ZH if lang == 'zh-HK' else WARM_SYSTEM_PROMPT_EN
    fallback = WARM_FALLBACK_ZH if lang == 'zh-HK' else WARM_FALLBACK_EN

    if not ZHIPU_API_KEY:
        return random.choice(fallback)

    history_key = (user_id, lang)
    if history_key not in user_api_histories:
        user_api_histories[history_key] = []
    history = user_api_histories[history_key]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-10:]) # Keep it lean for vision

    content = []
    if image_data:
        # User uploaded a photobook memory
        # Zhipu AI GLM-4v expects image_url in specific format
        content.append({
            "type": "text", 
            "text": f"這是一張老人家分享的照片，請根據圖片內容，用溫暖、關懷的語氣與他聊天。用戶說：{user_input}" if lang == 'zh-HK' else f"This is a photo shared by an elderly user. Please talk to them warmly about the image content. User said: {user_input}"
        })
        content.append({
            "type": "image_url", 
            "image_url": {"url": image_data}
        })
    else:
        content = user_input

    messages.append({"role": "user", "content": content})

    # Use glm-4v if image provided, else standard chat model
    model_name = "glm-4v-flash" if image_data else ZHIPU_MODEL

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1, # Lower temperature for faster, more focused vision response
        "top_p": 0.95,
        "max_tokens": 512,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ZHIPU_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {ZHIPU_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            result = resp.json()

        message = result.get("choices", [{}])[0].get("message", {})
        reply = message.get("content", "")

        if reply.strip():
            # Only store text content in history (save tokens/memory)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > 20:
                user_api_histories[history_key] = history[-10:]
            return reply
        else:
            raise ValueError("Empty response from API")

    except Exception as e:
        _builtins._original_print(f"[AI] Error calling Zhipu ({lang}): {e}")
        # Return a clearer error if it's an image memory request instead of a generic text fallback
        if image_data:
            return "啊，這張相片有啲睇唔清楚，你可以再發多一次俾我睇下嗎？" if lang == 'zh-HK' else "Oh, I couldn't quite see that photo. Could you try sending it again?"
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


# Start background reminder thread (Obsolete: Replaced by Lifespan task)
# if not ON_VERCEL:
#     threading.Thread(target=check_reminders, daemon=True).start()
# else:
#     print("[INFO] Vercel mode — background reminder thread disabled")

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
async def get_response(request: Request, msg: str = Form(...), file: Optional[UploadFile] = File(None)):
    """Process user message and return AI/command response.
    Photo Memories Integration: If file is provided, use vision model.
    """
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"response": "Please log in."}, status_code=401)

    lang = get_lang(request)
    user_input_original = msg.strip()
    user_input_lower = user_input_original.lower()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Handle Photo Memory upload
    # Zhipu GLM-4V expects pure base64 string. The 'data:image/...;base64,' prefix violates format causing 1210 error.
    image_base64 = None
    if file and file.content_type.startswith("image/"):
        contents = await file.read()
        image_base64 = base64.b64encode(contents).decode("utf-8")

    conn = get_db()
    c = conn.cursor()

    # Store user message
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
            # Validate time format (HH:MM) and parse hours/minutes
            h, m = map(int, time_str.split(':'))
            # Ensure valid 24-hour format (0-23 for hours, 0-59 for minutes)
            if 0 <= h <= 23 and 0 <= m <= 59:
                c.execute("INSERT INTO reminders (user_id, label, reminder_time, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                          (uid, label, time_str, timestamp))
                conn.commit()
                response = f"提醒已設置：{label}，時間 {time_str}" if lang == 'zh-HK' else f"Reminder set: {label} at {time_str}"
            else:
                response = "時間無效。請用24小時格式 HH:MM" if lang == 'zh-HK' else "Invalid time. Use 24-hour format HH:MM"
        except (ValueError, IndexError):
            # Handle malformed time strings (e.g., invalid separators, non-numeric values)
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
            response = await call_ai(user_input_original, uid, lang, image_data=image_base64)

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
    audio_bytes = await audio.read()

    # 1. Use OpenAI Whisper if API key is configured (Better for Cantonese/Accents)
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            import io
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.wav"
            print(f"[Whisper] Transcribing with OpenAI Whisper...")
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="zh"  # Setting to Chinese helps with Cantonese/Mandarin
            )
            return JSONResponse({"text": response.text.strip()})
        except Exception as e:
            print(f"[Whisper] Transcription error: {e}")
            # Fall through to Vosk if Whisper fails

    # 2. Fallback to Vosk offline English model
    model = get_vosk_model()
    if model is None:
        return JSONResponse({"text": "", "error": "STT model not available"})

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
@app.post("/register_device")
async def register_device(request: Request):
    try:
        data = await request.json()
        token = data.get("device_token")
        uid = get_user(request)
        if uid and token:
            # In a real setup, save this `token` to the database for this user
            print(f"[Push] Registered device token for {uid}: {token}")
            return JSONResponse({"status": "ok"})
    except:
        pass
    return JSONResponse({"status": "ignored"})

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
# HK Local Guide — Food, Shopping, Entertainment, Events
#
# Curated dataset of elderly-friendly HK local attractions with live
# refresh capability.  Data is cached for 30 minutes and can be force-
# refreshed from the client.  Each item has bilingual content.
# ---------------------------------------------------------------------------
_hk_guide_cache: dict = {"data": None, "timestamp": 0, "lang": None}

# Curated HK local guide data (bilingual)
HK_GUIDE_DATA = {
    "en": [
        # ---- FOOD ----
        {
            "category": "food",
            "name": "Tim Ho Wan — Dim Sum",
            "short_desc": "World's cheapest Michelin-star dim sum. Famous for baked BBQ pork buns.",
            "full_desc": "Tim Ho Wan is the most affordable Michelin-starred restaurant in the world. Known for their signature baked BBQ pork buns with a crispy, sweet top crust. The dim sum menu is extensive and everything is freshly made. Perfect for a casual, affordable fine-dining experience. Multiple branches across Hong Kong.",
            "location": "Sham Shui Po, Mong Kok, Central (multiple branches)",
            "price_range": "HK$50–150 per person",
            "hours": "10:00 AM – 9:30 PM daily",
            "transport": "MTR Sham Shui Po Station Exit B2 (original branch)",
            "elderly_friendly": True,
            "tips": ["Go early to avoid long queues", "Try the baked BBQ pork buns — their signature dish", "Most branches have elevator access"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Mak's Noodle — Wonton Noodles",
            "short_desc": "Legendary wonton noodles since 1920s. Thin, springy noodles with shrimp wontons.",
            "full_desc": "A Hong Kong institution for nearly 100 years, Mak's Noodle serves some of the best wonton noodles in the city. The hand-pulled noodles are thin and springy, served in a clear shrimp broth with plump shrimp wontons. Simple, affordable, and deeply satisfying.",
            "location": "Wellington Street, Central",
            "price_range": "HK$40–80 per person",
            "hours": "11:00 AM – 8:00 PM daily",
            "transport": "MTR Central Station Exit D2, 5 min walk",
            "elderly_friendly": True,
            "tips": ["Small portions — perfect for trying multiple dishes", "Cash preferred at some branches", "Air-conditioned seating available"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Tai Cheong Bakery — Egg Tarts",
            "short_desc": "Hong Kong's most famous egg tarts. Flaky crust, silky custard filling.",
            "full_desc": "Tai Cheong Bakery has been making egg tarts since 1954. The last British Governor Chris Patten was a loyal customer, earning them the nickname 'Governor's egg tarts'. The pastry has a perfectly flaky crust with smooth, lightly sweet egg custard. A must-try Hong Kong classic.",
            "location": "Lyndhurst Terrace, Central (original); multiple branches",
            "price_range": "HK$10–15 per tart",
            "hours": "7:30 AM – 9:00 PM daily",
            "transport": "MTR Central Station Exit D2",
            "elderly_friendly": True,
            "tips": ["Best eaten warm — ask for freshly baked ones", "Try the egg tarts with a cup of milk tea", "The Central branch is most iconic"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Australia Dairy Company",
            "short_desc": "Legendary cha chaan teng for scrambled eggs and milk pudding.",
            "full_desc": "This 1970s-style cha chaan teng (Hong Kong-style diner) is famous for their impossibly fluffy scrambled eggs on toast and silky steamed milk pudding. The service is famously fast and no-nonsense. Expect to share tables. A quintessential Hong Kong breakfast experience.",
            "location": "Jordan, Kowloon",
            "price_range": "HK$30–60 per person",
            "hours": "7:30 AM – 11:00 PM (closed Thursdays)",
            "transport": "MTR Jordan Station Exit C2",
            "elderly_friendly": True,
            "tips": ["Decide your order before sitting — service is lightning fast", "Must try: scrambled egg toast + milk tea", "Expect shared seating"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "Lei Yue Mun Seafood Village",
            "short_desc": "Pick-your-own live seafood village by the harbour. Fresh & affordable.",
            "full_desc": "Lei Yue Mun is a fishing village turned seafood haven where you can pick live seafood from market stalls and have nearby restaurants cook it for you. Enjoy the harbour views while dining on ultra-fresh fish, prawns, lobster, and crabs. A wonderful half-day outing combining market shopping and dining.",
            "location": "Lei Yue Mun, Kwun Tong, Kowloon",
            "price_range": "HK$150–400 per person",
            "hours": "11:00 AM – 10:00 PM daily",
            "transport": "MTR Yau Tong Station Exit A2, then minibus 24",
            "elderly_friendly": True,
            "tips": ["Compare prices at different stalls", "Cooking fee is separate from seafood cost", "Beautiful sunset views from the waterfront"],
            "url": "#"
        },
        # ---- SHOPPING ----
        {
            "category": "shopping",
            "name": "Ladies' Market — Tung Choi Street",
            "short_desc": "Bustling street market with bargains on clothing, accessories, souvenirs.",
            "full_desc": "Ladies' Market on Tung Choi Street stretches over a kilometre with hundreds of stalls selling affordable clothing, bags, accessories, phone cases, souvenirs, and everyday items. Despite the name, there's plenty for everyone. A lively, colourful market experience in the heart of Mong Kok.",
            "location": "Tung Choi Street, Mong Kok",
            "price_range": "HK$10–200 per item",
            "hours": "12:00 PM – 11:30 PM daily",
            "transport": "MTR Mong Kok Station Exit D3",
            "elderly_friendly": True,
            "tips": ["Bargaining is expected — start at 50% of asking price", "Best selection in the afternoon", "Watch for pickpockets in crowded areas"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Stanley Market",
            "short_desc": "Seaside market village with art, clothing, and waterfront restaurants.",
            "full_desc": "Stanley Market is a charming seaside market on the southern side of Hong Kong Island. Browse stalls selling art, silk garments, Chinese antiques, casual wear, and souvenirs. After shopping, enjoy seafood at the waterfront restaurants along Stanley Main Street. A relaxing half-day trip away from the city bustle.",
            "location": "Stanley, Hong Kong Island South",
            "price_range": "Varies widely",
            "hours": "10:00 AM – 6:00 PM daily",
            "transport": "Bus 6, 6X, 260 from Central (Exchange Square)",
            "elderly_friendly": True,
            "tips": ["Combine with a visit to Stanley Beach", "Waterfront restaurants have great views", "Less crowded on weekdays"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Jade Market — Yau Ma Tei",
            "short_desc": "Traditional jade jewellery market with hundreds of stalls of Chinese jade.",
            "full_desc": "The Jade Market in Yau Ma Tei has over 400 stalls selling jade jewellery, ornaments, and carvings. Jade holds deep cultural significance in Chinese tradition, symbolizing luck, health, and longevity. Whether you're looking for a small pendant or an elaborate jade bangle, this is the place. Adjacent to the equally fascinating Temple Street Night Market.",
            "location": "Kansu Street, Yau Ma Tei",
            "price_range": "HK$50–5,000+",
            "hours": "10:00 AM – 5:00 PM daily",
            "transport": "MTR Yau Ma Tei Station Exit C",
            "elderly_friendly": True,
            "tips": ["Bring cash for better deals", "Ask for certificates for expensive pieces", "Visit Temple Street Night Market nearby in the evening"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "Sham Shui Po Fabric & Electronics",
            "short_desc": "Budget paradise for fabrics, electronics, and vintage finds.",
            "full_desc": "Sham Shui Po is Hong Kong's most authentic working-class neighbourhood. It's a treasure trove for affordable fabrics, sewing supplies, beading materials, and budget electronics. Golden Computer Arcade and nearby shops sell electronics at rock-bottom prices. The area also has some of HK's best street food.",
            "location": "Sham Shui Po, Kowloon",
            "price_range": "Very affordable",
            "hours": "10:00 AM – 8:00 PM daily",
            "transport": "MTR Sham Shui Po Station Exit D2",
            "elderly_friendly": True,
            "tips": ["Check out the fabric shops on Ki Lung Street", "Try the street food on Kweilin Street", "Golden Computer Arcade for tech bargains"],
            "url": "#"
        },
        # ---- FUN & SIGHTS ----
        {
            "category": "fun",
            "name": "Victoria Peak — The Peak",
            "short_desc": "Iconic panoramic views of the Hong Kong skyline and harbour.",
            "full_desc": "The Peak is Hong Kong's most visited attraction, offering breathtaking 360-degree views of the city skyline, Victoria Harbour, and surrounding islands. Take the historic Peak Tram (Asia's oldest funicular railway, since 1888) to the top. The Sky Terrace 428 observation deck provides the best views. The Peak also has shops, restaurants, and easy walking paths.",
            "location": "The Peak, Hong Kong Island",
            "price_range": "Peak Tram: HK$62 (seniors HK$29)",
            "hours": "Peak Tram: 7:00 AM – 12:00 AM",
            "transport": "Peak Tram from Central (Garden Road terminal) or Bus 15 from Central",
            "elderly_friendly": True,
            "tips": ["Senior discount available with HKID", "Visit at sunset for the best views", "The circular walk around the Peak is flat and easy"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Star Ferry — Victoria Harbour",
            "short_desc": "Iconic harbour crossing since 1888. One of the world's best ferry rides.",
            "full_desc": "The Star Ferry has been crossing Victoria Harbour since 1888 and is one of Hong Kong's most beloved experiences. The 10-minute ride between Central and Tsim Sha Tsui offers stunning views of both shorelines. At just a few dollars per trip, it's one of the best bargains in Hong Kong. The Tsim Sha Tsui waterfront promenade is perfect for an evening stroll.",
            "location": "Central Pier ↔ Tsim Sha Tsui Pier",
            "price_range": "HK$3.70–5.60 (seniors HK$2.20)",
            "hours": "6:30 AM – 11:30 PM daily",
            "transport": "MTR Central Station Exit A or Tsim Sha Tsui Station Exit E",
            "elderly_friendly": True,
            "tips": ["Sit on the upper deck for best views", "Senior Octopus card gets discounted fare", "Best at sunset or for the Symphony of Lights at 8 PM"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Nan Lian Garden & Chi Lin Nunnery",
            "short_desc": "Tranquil Tang dynasty-style garden with bonsai, ponds, and a golden pagoda.",
            "full_desc": "Nan Lian Garden is a beautifully maintained Tang dynasty-style garden in the heart of urban Kowloon. Connected to the elegant Chi Lin Nunnery, the garden features manicured bonsai, lotus ponds, waterfalls, rocky hills, and the stunning golden Pavilion of Absolute Perfection. A serene escape from the city. Free entry.",
            "location": "Diamond Hill, Kowloon",
            "price_range": "Free entry",
            "hours": "7:00 AM – 9:00 PM daily",
            "transport": "MTR Diamond Hill Station Exit C2",
            "elderly_friendly": True,
            "tips": ["Completely free — one of HK's best free attractions", "Flat, wheelchair-accessible paths throughout", "Try the vegetarian restaurant inside Chi Lin Nunnery"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Hong Kong Wetland Park",
            "short_desc": "Nature reserve with bird-watching, butterfly gardens, and mangroves.",
            "full_desc": "Hong Kong Wetland Park is a 61-hectare nature reserve in Tin Shui Wai featuring indoor galleries, outdoor wetland habitats, bird hides, a butterfly garden, and mangrove boardwalks. Watch for the park's resident crocodile 'Pui Pui'. Educational and relaxing, it's a wonderful day out for nature lovers of all ages.",
            "location": "Tin Shui Wai, New Territories",
            "price_range": "HK$30 (seniors HK$15)",
            "hours": "10:00 AM – 5:00 PM (closed Tuesdays)",
            "transport": "MTR Wetland Park Station, 5 min walk",
            "elderly_friendly": True,
            "tips": ["Bring binoculars for bird-watching", "Flat boardwalks suitable for wheelchairs", "Best visited in autumn for migratory birds"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "Temple Street Night Market",
            "short_desc": "Atmospheric night market with food stalls, fortune tellers, and street opera.",
            "full_desc": "Temple Street Night Market comes alive after dark with hundreds of street stalls, open-air food vendors (try the clay pot rice and typhoon shelter crab), fortune tellers, and sometimes traditional Cantonese street opera. It's a vibrant window into old Hong Kong culture. The market is named after the Tin Hau Temple at its centre.",
            "location": "Temple Street, Yau Ma Tei & Jordan",
            "price_range": "HK$50–200 per person (food & shopping)",
            "hours": "4:00 PM – 12:00 AM daily (best after 7 PM)",
            "transport": "MTR Jordan Station Exit A or Yau Ma Tei Station Exit C",
            "elderly_friendly": True,
            "tips": ["Best atmosphere after 7 PM when fully open", "Try the dai pai dong street food near Temple Street", "Visit Tin Hau Temple for a cultural experience"],
            "url": "#"
        },
        # ---- EVENTS ----
        {
            "category": "events",
            "name": "Chinese New Year Celebrations 2026",
            "short_desc": "Fireworks, night parade, flower markets across Hong Kong.",
            "full_desc": "Chinese New Year 2026 (Year of the Horse) falls on 17 February. Key events include the spectacular fireworks display over Victoria Harbour, the international night parade in Tsim Sha Tsui, and traditional flower markets (年宵市場) across all districts. Victoria Park hosts the largest flower market. Temples are busy with worshippers on New Year's Day.",
            "location": "Citywide — Victoria Harbour, Tsim Sha Tsui, Victoria Park",
            "price_range": "Mostly free",
            "hours": "Various dates around 17 Feb 2026",
            "transport": "MTR to respective locations",
            "elderly_friendly": True,
            "tips": ["Flower markets start about a week before New Year", "Victoria Harbour fireworks best viewed from Tsim Sha Tsui waterfront", "Wear red for good luck!"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Cheung Chau Bun Festival 2026",
            "short_desc": "Unique annual festival with bun-snatching competition and Piu Sik parades.",
            "full_desc": "The Cheung Chau Bun Festival (太平清醮) is a unique annual Taoist festival held on the tiny island of Cheung Chau. Highlights include the famous bun-snatching competition where participants climb 14-metre bun towers, and the colourful Piu Sik (飄色) parade with children suspended in the air wearing elaborate costumes. A truly unique Hong Kong cultural experience.",
            "location": "Cheung Chau Island",
            "price_range": "Free (ferry ticket required)",
            "hours": "May 2026 (dates vary by lunar calendar)",
            "transport": "Ferry from Central Pier 5 to Cheung Chau (35-55 min)",
            "elderly_friendly": True,
            "tips": ["Arrive early — ferries get very crowded", "The island is small & walkable", "Try the festival buns (平安包) sold everywhere"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Mid-Autumn Festival Lantern Displays",
            "short_desc": "Spectacular lantern displays in Victoria Park and across HK districts.",
            "full_desc": "The Mid-Autumn Festival features stunning traditional and modern lantern displays across Hong Kong. Victoria Park hosts the largest display with themed lanterns, live performances, and traditional games. Many districts set up their own displays at local parks. People carry lanterns, eat mooncakes, and enjoy the full moon together. A wonderful family-friendly festival.",
            "location": "Victoria Park, Tai Hang (Fire Dragon), various districts",
            "price_range": "Free",
            "hours": "September 2026 (15th day of 8th lunar month)",
            "transport": "MTR Tin Hau Station for Victoria Park",
            "elderly_friendly": True,
            "tips": ["Don't miss the Tai Hang Fire Dragon Dance — a three-night tradition", "Try different mooncake flavours at local bakeries", "Bring a lantern to join the celebrations"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "Hong Kong Hiking Festival (Autumn)",
            "short_desc": "Organized senior-friendly hikes with guides on scenic HK trails.",
            "full_desc": "Autumn in Hong Kong (October–December) is the best hiking season with cool, dry weather. Many organizations host guided group hikes suitable for seniors, including easy routes along the Dragon's Back, Lamma Island Family Trail, and Tai Tam Reservoir path. These organized events often include transport, lunch, and experienced guides. A great way to socialize and stay active.",
            "location": "Various trails across Hong Kong",
            "price_range": "Free to HK$100 (organized events)",
            "hours": "October – December 2026",
            "transport": "Varies by trail",
            "elderly_friendly": True,
            "tips": ["Dragon's Back and Lamma Family Trail are easiest", "Bring water and wear comfortable shoes", "Check LCSD or hiking groups for organized senior events"],
            "url": "#"
        },
    ],
    "zh-HK": [
        # ---- 美食 ----
        {
            "category": "food",
            "name": "添好運 — 點心",
            "short_desc": "全球最平米芝蓮一星餐廳。招牌酥皮焗叉燒包好出名。",
            "full_desc": "添好運係全球最平嘅米芝蓮一星餐廳，招牌酥皮焗叉燒包外層酥脆帶甜，內餡叉燒鬆軟惹味。點心款式豐富，全部即點即蒸，新鮮熱辣。價錢親民，幾十蚊已經食到飽。分店遍布全港各區。",
            "location": "深水埗、旺角、中環（多間分店）",
            "price_range": "每位 HK$50–150",
            "hours": "每日 10:00 – 21:30",
            "transport": "港鐵深水埗站 B2 出口（原店）",
            "elderly_friendly": True,
            "tips": ["早啲去排隊會快好多", "一定要試招牌酥皮焗叉燒包", "大部分分店都有升降機"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "麥奀記 — 雲吞麵",
            "short_desc": "傳奇雲吞麵，1920年代至今。幼細彈牙竹昇麵配鮮蝦雲吞。",
            "full_desc": "麥奀記有近百年歷史，係香港最出名嘅雲吞麵之一。手打竹昇麵幼細彈牙，配上鮮甜蝦湯底同埋飽滿嘅鮮蝦雲吞。簡單、實惠、好食。每碗都係對傳統嘅堅持。",
            "location": "中環威靈頓街",
            "price_range": "每位 HK$40–80",
            "hours": "每日 11:00 – 20:00",
            "transport": "港鐵中環站 D2 出口，步行5分鐘",
            "elderly_friendly": True,
            "tips": ["份量唔大，啱晒一次試幾款", "部分分店淨收現金", "有冷氣座位"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "泰昌餅家 — 蛋撻",
            "short_desc": "全港最出名嘅蛋撻。酥皮鬆化，蛋漿嫩滑香甜。",
            "full_desc": "泰昌餅家自1954年開業，蛋撻係佢嘅招牌。末代港督彭定康都係佢嘅忠實粉絲，所以又叫做「肥彭蛋撻」。酥皮層層鬆化，蛋漿嫩滑帶甜，每一啖都充滿港式風味。必試之選。",
            "location": "中環擺花街（原店）；多間分店",
            "price_range": "每個蛋撻 HK$10–15",
            "hours": "每日 7:30 – 21:00",
            "transport": "港鐵中環站 D2 出口",
            "elderly_friendly": True,
            "tips": ["趁熱食最好味 — 可以問佢攞新鮮出爐嘅", "蛋撻配奶茶係絕配", "中環原店最有懷舊味"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "澳洲牛奶公司",
            "short_desc": "傳奇茶餐廳，炒蛋多士同燉奶極受歡迎。",
            "full_desc": "呢間70年代風格嘅茶餐廳以超滑炒蛋多士同蒸燉奶聞名。服務員出名快手快腳，坐低就要即叫。可能要同人搭枱。係最正宗嘅香港早餐體驗。",
            "location": "佐敦，九龍",
            "price_range": "每位 HK$30–60",
            "hours": "7:30 – 23:00（逢星期四休息）",
            "transport": "港鐵佐敦站 C2 出口",
            "elderly_friendly": True,
            "tips": ["坐低之前諗定叫咩 — 服務好快㗎", "必試：炒蛋多士 + 奶茶", "預咗要搭枱"],
            "url": "#"
        },
        {
            "category": "food",
            "name": "鯉魚門海鮮街",
            "short_desc": "自己揀活海鮮，對住海景食新鮮即煮海鮮。",
            "full_desc": "鯉魚門係一個漁村變成嘅海鮮天堂，可以喺海鮮檔揀活海鮮，然後拎到旁邊嘅食肆代煮。對住海港景色食新鮮魚、蝦、龍蝦、蟹，好寫意。係一個好適合半日遊嘅好去處。",
            "location": "鯉魚門，觀塘，九龍",
            "price_range": "每位 HK$150–400",
            "hours": "每日 11:00 – 22:00",
            "transport": "港鐵油塘站 A2 出口，轉小巴24",
            "elderly_friendly": True,
            "tips": ["多行幾檔比較價錢", "加工費同海鮮價錢係分開計", "黃昏景色特別靚"],
            "url": "#"
        },
        # ---- 購物 ----
        {
            "category": "shopping",
            "name": "女人街 — 通菜街",
            "short_desc": "旺角人氣露天市場，衫褲鞋襪飾物樣樣平。",
            "full_desc": "女人街喺通菜街，成個市場成成一公里長，有幾百個攤檔賣平價衫褲、手袋、飾物、手機殼、紀念品同日用品。雖然叫女人街，但係男女老幼都啱去。旺角最熱鬧嘅市集體驗。",
            "location": "旺角通菜街",
            "price_range": "每件 HK$10–200",
            "hours": "每日 12:00 – 23:30",
            "transport": "港鐵旺角站 D3 出口",
            "elderly_friendly": True,
            "tips": ["講價係常識，可以由一半開始還", "下晝先至最多嘢揀", "人多注意銀包財物"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "赤柱市場",
            "short_desc": "海邊市集，有藝術品、衫褲同海景餐廳。",
            "full_desc": "赤柱市場係港島南區嘅海邊市集，可以買到藝術品、絲綢衫、中式古董、休閒服同紀念品。行完街可以去海邊食海鮮，環境優美。離開市區半日遊好選擇。",
            "location": "赤柱，港島南",
            "price_range": "價錢唔一",
            "hours": "每日 10:00 – 18:00",
            "transport": "中環（交易廣場）搭巴士 6、6X、260",
            "elderly_friendly": True,
            "tips": ["順便去赤柱沙灘行吓", "海邊餐廳景色一流", "平日去人少好多"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "玉器市場 — 油麻地",
            "short_desc": "傳統玉器市場，有幾百個攤檔賣各式中國玉器。",
            "full_desc": "油麻地玉器市場有超過400個攤檔，賣玉器首飾、擺設同玉雕。玉器喺中國文化裏面代表好運、健康同長壽。無論係小吊墜定精緻玉鐲，呢度應有盡有。旁邊仲有廟街夜市。",
            "location": "油麻地甘肅街",
            "price_range": "HK$50–5,000+",
            "hours": "每日 10:00 – 17:00",
            "transport": "港鐵油麻地站 C 出口",
            "elderly_friendly": True,
            "tips": ["帶現金會有更好價錢", "貴嘅玉器記得要求證書", "晚上順便行廟街夜市"],
            "url": "#"
        },
        {
            "category": "shopping",
            "name": "深水埗布藝及電子商場",
            "short_desc": "平價天堂，布藝、電子產品同懷舊雜貨。",
            "full_desc": "深水埗係香港最地道嘅草根社區，平價布藝、製衣材料、珠仔材料同電子產品應有盡有。黃金電腦商場有最平嘅電子產品。呢區仲有好多好味街頭小食。",
            "location": "深水埗，九龍",
            "price_range": "非常平",
            "hours": "每日 10:00 – 20:00",
            "transport": "港鐵深水埗站 D2 出口",
            "elderly_friendly": True,
            "tips": ["基隆街一帶有最多布藝舖", "桂林街有好多街頭小食", "黃金電腦商場買電子嘢最平"],
            "url": "#"
        },
        # ---- 玩樂 ----
        {
            "category": "fun",
            "name": "太平山頂",
            "short_desc": "香港最著名嘅觀景點，可以睇到成個維港同城市景色。",
            "full_desc": "太平山頂係香港最受歡迎嘅景點，可以360度睇到城市天際線、維多利亞港同周圍嘅島嶼。搭歷史悠久嘅山頂纜車（亞洲最古老嘅纜索鐵路，1888年至今）上去。凌霄閣觀景台428係最佳觀景位置。山頂仲有商店、餐廳同易行嘅步行徑。",
            "location": "太平山，港島",
            "price_range": "山頂纜車：HK$62（長者 HK$29）",
            "hours": "山頂纜車：7:00 – 00:00",
            "transport": "中環花園道搭山頂纜車或中環搭巴士15號",
            "elderly_friendly": True,
            "tips": ["長者持香港身份證有優惠", "日落時分去景色最靚", "環山步行徑平坦易行"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "天星小輪 — 維多利亞港",
            "short_desc": "1888年至今嘅經典渡輪，世界最佳渡輪體驗之一。",
            "full_desc": "天星小輪自1888年穿梭維港，係香港最受歡迎嘅體驗之一。10分鐘嘅船程由中環去到尖沙咀，兩岸景色盡收眼底。幾蚊雞就搭到，性價比極高。尖沙咀海濱長廊好適合傍晚散步。",
            "location": "中環碼頭 ↔ 尖沙咀碼頭",
            "price_range": "HK$3.70–5.60（長者 HK$2.20）",
            "hours": "每日 6:30 – 23:30",
            "transport": "港鐵中環站 A 出口或尖沙咀站 E 出口",
            "elderly_friendly": True,
            "tips": ["坐上層景色最好", "長者八達通有優惠", "日落或晚上8點幻彩詠香江最靚"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "南蓮園池 & 志蓮淨苑",
            "short_desc": "寧靜唐式園林，有盆景、荷花池同金色涼亭。",
            "full_desc": "南蓮園池係一個保養得好靚嘅唐朝風格園林，位於城市中心嘅鑽石山。連住典雅嘅志蓮淨苑，園內有精心修剪嘅盆景、荷花池、瀑布、假山同華麗嘅金色圓滿閣。城市中嘅寧靜角落。免費入場。",
            "location": "鑽石山，九龍",
            "price_range": "免費入場",
            "hours": "每日 7:00 – 21:00",
            "transport": "港鐵鑽石山站 C2 出口",
            "elderly_friendly": True,
            "tips": ["完全免費，係香港最佳免費景點之一", "全園平坦，輪椅都行到", "可以試吓志蓮淨苑入面嘅素食餐廳"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "香港濕地公園",
            "short_desc": "自然保護區，有觀鳥、蝴蝶園同紅樹林木板步道。",
            "full_desc": "香港濕地公園位於天水圍，佔地61公頃，有室內展覽館、戶外濕地生態、觀鳥屋、蝴蝶園同紅樹林步道。仲可以睇到公園嘅明星鱷魚「貝貝」。既有教育意義又輕鬆寫意，適合各年齡層嘅自然愛好者。",
            "location": "天水圍，新界",
            "price_range": "HK$30（長者 HK$15）",
            "hours": "10:00 – 17:00（逢星期二休園）",
            "transport": "港鐵濕地公園站，步行5分鐘",
            "elderly_friendly": True,
            "tips": ["帶望遠鏡觀鳥更有趣", "木板步道平坦，輪椅都行到", "秋天嚟最好，可以睇到候鳥"],
            "url": "#"
        },
        {
            "category": "fun",
            "name": "廟街夜市",
            "short_desc": "有氣氛嘅夜市，有街頭小食、占卜同粵劇。",
            "full_desc": "廟街夜市天黑後最熱鬧，有幾百個街邊攤檔、露天大牌檔（試吓煲仔飯同避風塘炒蟹）、占卜攤同偶爾嘅粵劇表演。係睇舊香港文化嘅好地方。夜市以中間嘅天后廟命名。",
            "location": "廟街，油麻地及佐敦",
            "price_range": "每位 HK$50–200（食嘢同購物）",
            "hours": "每日 16:00 – 00:00（19:00後最旺）",
            "transport": "港鐵佐敦站 A 出口或油麻地站 C 出口",
            "elderly_friendly": True,
            "tips": ["晚上7點後最有氣氛", "試吓廟街附近嘅大牌檔小食", "去天后廟參拜感受文化"],
            "url": "#"
        },
        # ---- 活動 ----
        {
            "category": "events",
            "name": "2026 農曆新年慶祝活動",
            "short_desc": "維港煙花、花車巡遊、年宵花市遍布全港。",
            "full_desc": "2026年農曆新年（馬年）喺2月17日。重點活動包括維港上空嘅壯觀煙花匯演、尖沙咀國際花車巡遊、同遍布全港嘅年宵花市。維園有最大嘅花市。年初一各大廟宇會好多人拜神。",
            "location": "全港 — 維港、尖沙咀、維園",
            "price_range": "大部分免費",
            "hours": "2026年2月17日前後",
            "transport": "港鐵到相關地點",
            "elderly_friendly": True,
            "tips": ["年宵花市喺新年前一個禮拜開始", "維港煙花喺尖沙咀海邊睇最靚", "著紅色衫代表好運！"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "2026 長洲太平清醮",
            "short_desc": "獨特年度節慶，有搶包山比賽同飄色巡遊。",
            "full_desc": "長洲太平清醮係一個好特別嘅年度道教節日，喺長洲島舉行。重點包括出名嘅搶包山比賽（參加者要爬上14米高嘅包山）同色彩繽紛嘅飄色巡遊（小朋友著住靚衫凌空飛起）。真係獨一無二嘅香港文化體驗。",
            "location": "長洲島",
            "price_range": "免費（需要買船票）",
            "hours": "2026年5月（日期按農曆定）",
            "transport": "中環5號碼頭搭渡輪去長洲（35-55分鐘）",
            "elderly_friendly": True,
            "tips": ["早啲去碼頭，船會好迫", "島仔唔大，行路就得", "記得買「平安包」食"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "中秋節花燈會",
            "short_desc": "維園同各區公園嘅大型花燈展覽。",
            "full_desc": "中秋節有壯觀嘅傳統同現代花燈展覽遍布全港。維園有最大型嘅花燈會，有主題花燈、現場表演同傳統遊戲。好多區都會喺當地公園搞花燈展。市民會提燈籠、食月餅、賞月。好適合一家大細嘅節日。",
            "location": "維園、大坑（舞火龍）、各區",
            "price_range": "免費",
            "hours": "2026年9月（農曆八月十五）",
            "transport": "港鐵天后站去維園",
            "elderly_friendly": True,
            "tips": ["一定唔好錯過大坑舞火龍 — 一連三晚嘅傳統", "試吓唔同口味嘅月餅", "帶個燈籠一齊玩"],
            "url": "#"
        },
        {
            "category": "events",
            "name": "秋季香港行山節",
            "short_desc": "有導賞嘅長者友善行山團，行香港靚景山徑。",
            "full_desc": "香港秋天（10至12月）係最佳行山季節，天氣涼爽乾燥。好多機構會搞適合長者嘅導賞行山團，包括輕鬆路線如龍脊、南丫島家樂徑同大潭水塘路。有啲活動包交通、午餐同經驗豐富嘅導遊。係保持活躍同社交嘅好方法。",
            "location": "全港各行山徑",
            "price_range": "免費至 HK$100（有組織活動）",
            "hours": "2026年10月至12月",
            "transport": "視乎路線而定",
            "elderly_friendly": True,
            "tips": ["龍脊同南丫島家樂徑最輕鬆", "記得帶水同著舒服嘅鞋", "留意康文署或行山群組嘅長者活動"],
            "url": "#"
        },
    ]
}


def get_hk_guide_data(lang: str = 'en') -> list[dict]:
    """Return curated HK local guide data for the given language."""
    return HK_GUIDE_DATA.get(lang, HK_GUIDE_DATA["en"])


@app.get("/hk_guide", response_class=HTMLResponse)
async def hk_guide_page(request: Request):
    """Render the HK Local Guide page."""
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("hk_guide.html", tpl_context(request))


@app.get("/get_hk_guide")
async def get_hk_guide(request: Request, refresh: int = 0):
    """Return HK local guide data as JSON (cached 30 min)."""
    import time as _time
    lang = get_lang(request)
    now = _time.time()

    # Use cache unless forced refresh
    if (not refresh
            and _hk_guide_cache["data"]
            and (now - _hk_guide_cache["timestamp"]) < 1800
            and _hk_guide_cache["lang"] == lang):
        return JSONResponse(_hk_guide_cache["data"])

    items = get_hk_guide_data(lang)
    ts_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    result = {
        "items": items,
        "last_updated": ts_str,
        "total": len(items),
    }
    _hk_guide_cache["data"] = result
    _hk_guide_cache["timestamp"] = now
    _hk_guide_cache["lang"] = lang
    return JSONResponse(result)

# ---------------------------------------------------------------------------
# Development server entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    import builtins as _builtins
    # Restore original print for the concise startup message (if it exists)
    try:
        _builtins.print = _builtins._original_print
    except Exception:
        pass

    port = int(os.environ.get("PORT", 5000))
    url = f"http://localhost:{port}"
    print(f"Server running: {url}")

    # Run Uvicorn with quieter logging. Access logs and INFO-level logs are
    # disabled to keep console output minimal.
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", access_log=False)