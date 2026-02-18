from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
import os
import json
import sqlite3
from datetime import datetime
import threading
import secrets
import random
import urllib.request
from translations import get_text, get_all_translations, TRANSLATIONS

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# =============================================================================
# WTForms
# =============================================================================
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", (email.data,))
        if c.fetchone():
            conn.close()
            raise ValidationError('Email already exists')
        conn.close()

# =============================================================================
# Global State
# =============================================================================
user_game_states = {}
user_api_histories = {}  # (user_id, lang) -> conversation history list

CHAT_HISTORY_RETENTION_MINUTES = 30

# =============================================================================
# AI Configuration (ZhipuAI GLM-4-Flash API - FREE)
# GLM-4-Flash: FREE model with conversational abilities, supports both
# English and Chinese. Lightweight and fast, perfect for elderly companion chat.
# Both English and Chinese chat use this API, keeping the project lightweight
# for deployment on free hosting plans (Render, etc.)
# Get your free API key at: https://open.bigmodel.cn
# =============================================================================
AI_API_KEY = os.environ.get('ZHIPUAI_API_KEY', 'REDACTED_ZHIPU_API_KEY.REDACTED_ZHIPU_SUFFIX')
AI_BASE_URL = os.environ.get('ZHIPUAI_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')
AI_MODEL = os.environ.get('ZHIPUAI_MODEL', 'glm-4-flash')

if AI_API_KEY:
    print(f"✓ AI ({AI_MODEL}) API configured for both English and Chinese")
else:
    print("⚠ ZHIPUAI_API_KEY not set - chat will use warm fallback responses")
    print("  Get your FREE key at: https://open.bigmodel.cn")

print("✓ Speech recognition uses browser Web Speech API (zero server deps)")

# Warm system prompt for Chinese (Cantonese-style elderly companion)
WARM_SYSTEM_PROMPT_ZH = """你是一個非常溫暖、親切、有耐心的陪伴者，專門陪老人家聊天，稱呼對方為朋友。

你的說話風格：
- 語氣溫柔、充滿關懷，像孫仔女咁同老人家傾偈
- 說話簡單易明，唔用複雜詞語
- 經常表達關心："你今日點呀？" "食咗飯未？" "有冇瞓得好？"
- 多用正面鼓勵嘅說話
- 如果老人家講唔清楚或重複問題，要非常有耐心，唔好表現出不耐煩
- 多用 "好呀"、"真係好"、"你真係叻" 等鼓勵說話
- 偶爾分享溫馨小故事或回憶往事
- 回覆保持簡短（2-4句），易讀易明

IMPORTANT: 直接回答用戶的問題，不要顯示你的思考過程或分析步驟。

記住：你的目標是讓老人家感到溫暖、被關心、唔孤單。"""

# Warm system prompt for English elderly companion
WARM_SYSTEM_PROMPT_EN = """You are a very warm, kind, and patient companion who chats with elderly people.

Your speaking style:
- Gentle and caring tone, like a grandchild talking with their grandparent
- Use simple, easy-to-understand language
- Frequently express concern: "How are you today?" "Have you eaten?" "Did you sleep well?"
- Use positive encouragement and uplifting words
- Be very patient if the user is unclear or repeats questions - never show impatience
- Use phrases like "That's wonderful!", "I'm so glad to hear that!", "You're doing great!"
- Occasionally share warm stories or reminisce about good times
- Keep responses short (2-4 sentences), easy to read and understand

IMPORTANT: Answer the user's questions directly without showing your reasoning process or analysis steps.

Remember: Your goal is to make elderly people feel warm, cared for, and less lonely."""

# Warm fallback responses (used when API key is not configured)
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

def call_ai(user_input, user_id, lang='en'):
    """Call ZhipuAI GLM-4-Flash API for warm elderly conversation.
    Supports both English and Chinese with appropriate system prompts.
    Falls back to warm template responses if API is not configured."""
    system_prompt = WARM_SYSTEM_PROMPT_ZH if lang == 'zh-HK' else WARM_SYSTEM_PROMPT_EN
    fallback = WARM_FALLBACK_ZH if lang == 'zh-HK' else WARM_FALLBACK_EN

    if not AI_API_KEY:
        return random.choice(fallback)

    # Get or create conversation history per user per language
    history_key = (user_id, lang)
    if history_key not in user_api_histories:
        user_api_histories[history_key] = []
    history = user_api_histories[history_key]

    # Build messages with system prompt + recent history
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-20:])  # Last 10 exchanges
    messages.append({"role": "user", "content": user_input})

    try:
        url = f"{AI_BASE_URL}/chat/completions"
        data = json.dumps({
            "model": AI_MODEL,
            "messages": messages,
            "temperature": 0.8,
            "top_p": 0.9,
            "max_tokens": 256,
            "reasoning": False  # Disable reasoning mode for direct responses
        }).encode('utf-8')

        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        })

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            message = result["choices"][0]["message"]
            # GLM-4.7-Flash may use reasoning_content for detailed responses
            reply = message.get("content") or message.get("reasoning_content", "")

        # Update conversation history
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})
        if len(history) > 30:
            user_api_histories[history_key] = history[-20:]

        return reply

    except Exception as e:
        print(f"[AI] API error ({lang}): {e}")
        return random.choice(fallback)

# Chinese quiz questions
questions_zh = [
    {"question": "法國嘅首都係邊度？", "answer": "巴黎"},
    {"question": "2 + 2 等於幾多？", "answer": "4"},
    {"question": "晴天嘅天空係咩顏色？", "answer": "藍色"},
    {"question": "有一種水果，外面紅色，入面白色，有好多黑色嘅籽。係咩嚟㗎？", "answer": "西瓜"},
    {"question": "邊個月份有28日？", "answer": "每個月都有至少28日"},
    {"question": "水嘅化學符號係咩？", "answer": "h2o"},
]

# =============================================================================
# Quiz Questions
# =============================================================================
questions = [
    {"question": "What's the capital of France?", "answer": "paris"},
    {"question": "What's 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"},
    {"question": "There is a fruit with a red outer skin and white inside with small black seeds. What is it?", "answer": "watermelon"},
    {"question": "Which month has 28 days?", "answer": "every month has at least 28 days"},
    {"question": "What is the chemical symbol for water?", "answer": "h2o"}
]

# =============================================================================
# Database Setup
# =============================================================================
def init_db():
    # Create tables with improved structure
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()

    # Users table - stores user authentication and profile data
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )""")

    # Reminders table - daily reminders with auto-expiration support
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

    # Chat history - conversation logs with soft delete capability
    c.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_bot BOOLEAN NOT NULL,
        message TEXT NOT NULL,
        is_deleted BOOLEAN DEFAULT 0,
        token_count INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Preferences - user-specific settings
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

    # Create indexes for better query performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, is_active)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_deleted ON chat_history(user_id, is_deleted)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pref_user ON preferences(user_id, pref_key)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(user_id, created_at)')

    conn.commit()
    conn.close()
    print("[DB] ✅ Database initialized with improved structure")

init_db()

# =============================================================================
# Helper Functions
# =============================================================================
def cleanup_old_chat_history():
    # Auto-cleanup chat messages older than retention period (soft delete)
    # Runs periodically to maintain database performance
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    cutoff_time = datetime.now().timestamp() - (CHAT_HISTORY_RETENTION_MINUTES * 60)
    cutoff_datetime = datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d %H:%M:%S')

    c.execute("""UPDATE chat_history SET is_deleted = 1
                 WHERE timestamp < ? AND is_deleted = 0""", (cutoff_datetime,))

    deleted_count = c.rowcount
    conn.commit()
    conn.close()

    if deleted_count > 0:
        print(f"[CLEANUP] 🗑️  Marked {deleted_count} old messages as deleted")

def auto_expire_old_reminders():
    # Automatically expire reminders from previous days
    # This ensures only today's reminders are shown while preserving history
    # Reminders are marked inactive but not deleted from database
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Mark reminders created before today as inactive
    c.execute("""
        UPDATE reminders 
        SET is_active = 0, updated_at = ?
        WHERE DATE(created_at) < ? 
        AND is_active = 1
    """, (current_timestamp, today))

    expired_count = c.rowcount
    conn.commit()
    conn.close()

    if expired_count > 0:
        print(f"[EXPIRE] 📅 Marked {expired_count} old reminders as inactive")

    return expired_count

# =============================================================================
# Background Tasks
# =============================================================================
def check_reminders():
    # Background daemon thread that performs periodic maintenance:
    # 1. Check and trigger active reminders at scheduled times
    # 2. Auto-expire old reminders (hourly)
    # 3. Cleanup old chat history (every 10 minutes)
    while True:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M')

        # Only check today's active reminders for triggering
        c.execute("""
            SELECT u.email, r.label, r.reminder_time
            FROM reminders r
            JOIN users u ON r.user_id = u.id
            WHERE r.is_active = 1 
            AND DATE(r.created_at) = ?
        """, (today,))

        reminders = c.fetchall()

        for email, label, reminder_time in reminders:
            if reminder_time == current_time:
                print(f"[REMINDER] ⏰ {email}: {label} at {reminder_time}")

        conn.close()

        # Auto-expire old reminders every hour at minute 0
        if datetime.now().minute == 0:
            auto_expire_old_reminders()

        # Cleanup old chat history every 10 minutes
        if datetime.now().minute % 10 == 0:
            cleanup_old_chat_history()

        threading.Event().wait(60)

# Start background maintenance thread
threading.Thread(target=check_reminders, daemon=True).start()

# =============================================================================
# Authentication
# =============================================================================
def login_required(f):
    # Decorator to protect routes that require authentication
    def wrap(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    lang = session.get('language', 'en')
    if form.validate_on_submit():
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)",
                     (form.email.data, form.password.data, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            flash(get_text('register_success', lang) if lang == 'zh-HK' else 'Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash(get_text('email_exists', lang) if lang == 'zh-HK' else 'Email already exists', 'danger')
        finally:
            conn.close()
    return render_template('register.html', form=form, lang=lang, translations=get_all_translations(lang))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    lang = session.get('language', 'en')
    if form.validate_on_submit():
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT id, email FROM users WHERE email = ? AND password = ?",
                 (form.email.data, form.password.data))
        user = c.fetchone()

        if user:
            # Update last login timestamp
            c.execute("UPDATE users SET last_login = ? WHERE id = ?",
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user[0]))
            conn.commit()

            session['user_email'] = user[1]
            session['user_id'] = user[0]
            
            # Load user's saved language preference
            c.execute("SELECT pref_value FROM preferences WHERE user_id = ? AND pref_key = 'language'", (user[0],))
            pref = c.fetchone()
            if pref:
                session['language'] = pref[0]
            
            flash('Login successful!' if lang == 'en' else '登入成功！', 'success')
            conn.close()
            return redirect(url_for('index'))

        conn.close()
        flash('Invalid email or password' if lang == 'en' else '電郵或密碼錯誤', 'danger')
    return render_template('login.html', form=form, lang=lang, translations=get_all_translations(lang))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    flash("Forgot password feature is coming soon!", "info")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # Get user language preference (default to 'en')
    lang = session.get('language', 'en')
    return render_template('chat.html', lang=lang, translations=get_all_translations(lang))

@app.route('/set_language/<lang>')
def set_language(lang):
    """Set user's language preference (works for both logged-in and anonymous users)"""
    if lang in ['en', 'zh-HK']:
        session['language'] = lang
        
        # Save to database if user is logged in
        if 'user_id' in session:
            user_id = session['user_id']
            conn = sqlite3.connect('reminders.db')
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO preferences (user_id, pref_key, pref_value, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, 'language', lang, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            conn.close()
    
    return redirect(request.referrer or url_for('login'))

@app.route('/accessibility')
@login_required
def accessibility_mode():
    """Accessibility mode with large buttons, high contrast, and voice-first interaction"""
    lang = session.get('language', 'en')
    return render_template('accessibility.html', lang=lang, translations=get_all_translations(lang))

@app.route('/guidance')
@login_required
def guidance():
    """Guidance page with examples and instructions"""
    lang = session.get('language', 'en')
    return render_template('guidance.html', lang=lang, translations=get_all_translations(lang))

# =============================================================================
# Chat Response
# =============================================================================
@app.route('/get_response', methods=['POST'])
@login_required
def get_response():
    user_id = session['user_id']

    # Preserve original input with proper capitalization for AI model
    user_input_original = request.form['msg'].strip()

    # Create lowercase version for command matching only
    user_input_lower = user_input_original.lower()

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()

    # Store original user message (preserving case for better AI context)
    c.execute(
        "INSERT INTO chat_history (user_id, timestamp, is_bot, message, is_deleted) VALUES (?, ?, 0, ?, 0)",
        (user_id, timestamp, user_input_original)
    )
    conn.commit()

    response = ""

    # --------------------- Reminder Commands ---------------------
    # Support both English and Chinese commands
    if user_input_lower.startswith("set reminder") or user_input_lower.startswith("設置提醒"):
        if user_input_lower.startswith("設置提醒"):
            parts = user_input_original.split()
            if len(parts) >= 3 and ':' in parts[-1]:
                time_str = parts[-1]
                label = ' '.join(parts[1:-1])
            else:
                response = "格式：設置提醒 [活動] [HH:MM]"
                c.execute("INSERT INTO chat_history (user_id, timestamp, is_bot, message, is_deleted) VALUES (?, ?, 1, ?, 0)", (user_id, timestamp, response))
                conn.commit()
                conn.close()
                return jsonify({'response': response})
        else:
            parts = user_input_lower.split()
            if len(parts) >= 4 and len(parts[-1]) == 5 and parts[-1][2] == ':':
                time_str = parts[-1]
                label = ' '.join(parts[2:-1])
            else:
                response = "Usage: set reminder [activity] [HH:MM]"
                c.execute("INSERT INTO chat_history (user_id, timestamp, is_bot, message, is_deleted) VALUES (?, ?, 1, ?, 0)", (user_id, timestamp, response))
                conn.commit()
                conn.close()
                return jsonify({'response': response})

        try:
            h, m = map(int, time_str.split(':'))
            if 0 <= h <= 23 and 0 <= m <= 59:
                c.execute(
                    "INSERT INTO reminders (user_id, label, reminder_time, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (user_id, label, time_str, timestamp)
                )
                conn.commit()
                lang = session.get('language', 'en')
                if lang == 'zh-HK':
                    response = f"提醒已設置：{label}，時間 {time_str}"
                else:
                    response = f"Reminder set: {label} at {time_str}"
            else:
                response = "Invalid time. Use 24-hour format HH:MM" if session.get('language', 'en') == 'en' else "時間無效。請用24小時格式 HH:MM"
        except:
            response = "Invalid time format. Use HH:MM" if session.get('language', 'en') == 'en' else "時間格式錯誤。請用 HH:MM"

    elif user_input_lower.startswith("delete reminder") or user_input_lower.startswith("刪除提醒"):
        if user_input_lower.startswith("刪除提醒"):
            parts = user_input_original.split(maxsplit=1)
            label = parts[1] if len(parts) == 2 else None
        else:
            parts = user_input_lower.split(maxsplit=2)
            label = parts[2] if len(parts) == 3 else None

        if label:
            c.execute("DELETE FROM reminders WHERE user_id = ? AND label = ?", (user_id, label))
            if c.rowcount > 0:
                response = f"已刪除提醒：{label}" if session.get('language', 'en') == 'zh-HK' else f"Deleted reminder: {label}"
            else:
                response = "找不到該提醒。" if session.get('language', 'en') == 'zh-HK' else "No reminder found with that name."
            conn.commit()
        else:
            response = "格式：刪除提醒 [活動]" if session.get('language', 'en') == 'zh-HK' else "Usage: delete reminder [activity]"

    # --------------------- Preferences ---------------------
    elif user_input_lower.startswith("set preference"):
        parts = user_input_lower.split(maxsplit=4)
        if len(parts) >= 4:
            key, value = parts[2], parts[3]
            c.execute(
                "INSERT OR REPLACE INTO preferences (user_id, pref_key, pref_value, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, key, value, timestamp)
            )
            conn.commit()
            response = f"Preference updated: {key} = {value}"
        else:
            response = "Usage: set preference [key] [value]"

    # --------------------- Quiz Game ---------------------
    else:
        lang = session.get('language', 'en')
        active_questions = questions_zh if lang == 'zh-HK' else questions
        
        game = user_game_states.setdefault(user_id, {
            'is_game_mode': False,
            'current_index': 0,
            'current_question': None,
            'correct_answer': None,
            'score': 0
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
            # Compare answers in lowercase for case-insensitive matching
            if user_input_lower.strip() == game['correct_answer']:
                game['score'] += 1
                response = f"正確！分數：{game['score']}" if lang == 'zh-HK' else f"Correct! Score: {game['score']}"
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

        # --------------------- Normal AI Chat ---------------------
        else:
            response = call_ai(user_input_original, user_id, lang)

    # Store bot response in database
    c.execute(
        "INSERT INTO chat_history (user_id, timestamp, is_bot, message, is_deleted) VALUES (?, ?, 1, ?, 0)",
        (user_id, timestamp, response)
    )
    conn.commit()
    conn.close()

    return jsonify({'response': response})

# =============================================================================
# Reminder Management
# =============================================================================
@app.route('/deactivate_reminder', methods=['POST'])
@login_required
def deactivate_reminder():
    # Manually deactivate a specific reminder
    user_id = session['user_id']
    label = request.form['label']

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute(
        "UPDATE reminders SET is_active = 0, updated_at = ? WHERE user_id = ? AND label = ?",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, label)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True})

# =============================================================================
# API Endpoints
# =============================================================================
@app.route('/get_reminders', methods=['GET'])
@login_required
def get_reminders():
    # Fetch reminders for current user
    # Returns only today's reminders to keep UI clean
    # Historical reminders remain in database but are not displayed
    user_id = session['user_id']

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()

    # Get today's date for filtering
    today = datetime.now().strftime('%Y-%m-%d')

    # Only fetch reminders created today
    c.execute("""
        SELECT label, reminder_time, is_active, created_at 
        FROM reminders 
        WHERE user_id = ? 
        AND DATE(created_at) = ?
        ORDER BY created_at DESC
    """, (user_id, today))

    reminders = [{
        "label": r[0], 
        "time": r[1], 
        "active": bool(r[2])
    } for r in c.fetchall()]

    conn.close()

    return jsonify({'reminders': reminders})

@app.route('/get_chat_history', methods=['GET'])
@login_required
def get_chat_history():
    # Fetch chat history for current user (excluding deleted messages)
    user_id = session['user_id']

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("""
        SELECT timestamp, is_bot, message 
        FROM chat_history 
        WHERE user_id = ? AND is_deleted = 0 
        ORDER BY timestamp
    """, (user_id,))

    history = [{
        "timestamp": r[0], 
        "sender": "bot" if r[1] else "user",
        "message": r[2]
    } for r in c.fetchall()]

    conn.close()

    return jsonify({'history': history})

# =============================================================================
# Run Server
# =============================================================================
if __name__ == '__main__':
    print("=" * 70)
    print("Elderly Companion Chatbot - Lightweight Cloud Edition")
    print("=" * 70)
    print(f"[INFO] \u2705 AI Model: {AI_MODEL} (ZhipuAI API)")
    print(f"[INFO] \u2705 Chat history retention: {CHAT_HISTORY_RETENTION_MINUTES} minutes")
    print(f"[INFO] \u2705 Voice: Browser Web Speech API (EN + zh-HK)")
    print(f"[INFO] \u2705 No heavy dependencies (PyTorch/Vosk removed)")
    print("=" * 70)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)