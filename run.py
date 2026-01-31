from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
import json
import io
import sqlite3
from datetime import datetime
import threading
import secrets
from vosk import Model, KaldiRecognizer
from pydub import AudioSegment

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
user_chat_histories = {}
user_game_states = {}

# =============================================================================
# Model Loading
# =============================================================================
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

EN_MODEL_PATH = os.path.join('voice_models', 'vosk-model-small-en-us-0.15')
vosk_model = Model(EN_MODEL_PATH)

MAX_HISTORY_TOKENS = 1024
CHAT_HISTORY_RETENTION_MINUTES = 30

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
# Database (IMPROVED STRUCTURE)
# =============================================================================
def init_db():
    """Create tables with improved structure."""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()

    # Users table
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )""")

    # Reminders table
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

    # Chat history
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

    # Preferences
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

    # Create indexes for better performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, is_active)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chat_deleted ON chat_history(user_id, is_deleted)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pref_user ON preferences(user_id, pref_key)')

    conn.commit()
    conn.close()
    print("[DB] ✅ Database initialized with improved structure")

init_db()

# =============================================================================
# Helper Functions
# =============================================================================
def cleanup_old_chat_history():
    """Auto-cleanup chat messages older than retention period (soft delete)"""
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

# =============================================================================
# Background Tasks
# =============================================================================
def check_reminders():
    """Background thread: check reminders and cleanup old chat history"""
    while True:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("""SELECT u.email, r.label, r.reminder_time
                     FROM reminders r
                     JOIN users u ON r.user_id = u.id
                     WHERE r.is_active = 1""")
        reminders = c.fetchall()
        current_time = datetime.now().strftime('%H:%M')

        for email, label, reminder_time in reminders:
            if reminder_time == current_time:
                print(f"[REMINDER] ⏰ {email}: {label} at {reminder_time}")

        conn.close()

        # Cleanup old chat history every 10 minutes
        if datetime.now().minute % 10 == 0:
            cleanup_old_chat_history()

        threading.Event().wait(60)

threading.Thread(target=check_reminders, daemon=True).start()

# =============================================================================
# Authentication
# =============================================================================
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (email, password, created_at) VALUES (?, ?, ?)",
                     (form.email.data, form.password.data, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists', 'danger')
        finally:
            conn.close()
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
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
            flash('Login successful!', 'success')
            conn.close()
            return redirect(url_for('index'))

        conn.close()
        flash('Invalid email or password', 'danger')
    return render_template('login.html', form=form)

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
    return render_template('chat.html')

# =============================================================================
# Chat Response (FIXED: Preserve capitalization for better AI quality)
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
    if user_input_lower.startswith("set reminder"):
        parts = user_input_lower.split()
        if len(parts) >= 4 and len(parts[-1]) == 5 and parts[-1][2] == ':':
            time_str = parts[-1]
            label = ' '.join(parts[2:-1])
            try:
                h, m = map(int, time_str.split(':'))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    c.execute(
                        "INSERT INTO reminders (user_id, label, reminder_time, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                        (user_id, label, time_str, timestamp)
                    )
                    conn.commit()
                    response = f"Reminder set: {label} at {time_str}"
                else:
                    response = "Invalid time. Use 24-hour format HH:MM"
            except:
                response = "Invalid time format. Use HH:MM"
        else:
            response = "Usage: set reminder [activity] [HH:MM]"

    elif user_input_lower.startswith("delete reminder"):
        parts = user_input_lower.split(maxsplit=2)
        if len(parts) == 3:
            label = parts[2]
            c.execute("DELETE FROM reminders WHERE user_id = ? AND label = ?", (user_id, label))
            if c.rowcount > 0:
                response = f"Deleted reminder: {label}"
            else:
                response = "No reminder found with that name."
            conn.commit()
        else:
            response = "Usage: delete reminder [activity]"

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
        game = user_game_states.setdefault(user_id, {
            'is_game_mode': False,
            'current_index': 0,
            'current_question': None,
            'correct_answer': None,
            'score': 0
        })

        if user_input_lower == "play game" and not game['is_game_mode']:
            game['is_game_mode'] = True
            game['current_index'] = 0
            game['score'] = 0
            q = questions[0]
            game['current_question'] = q["question"]
            game['correct_answer'] = q["answer"]
            response = f"Let's play! You have {len(questions)} questions. Current score: 0. First question: {game['current_question']}"

        elif user_input_lower == "exit game" and game['is_game_mode']:
            game['is_game_mode'] = False
            response = f"Game stopped. You got {game['score']} out of {game['current_index']} correct so far!"

        elif game['is_game_mode']:
            # Compare answers in lowercase for case-insensitive matching
            if user_input_lower.strip() == game['correct_answer']:
                game['score'] += 1
                response = f"Correct! Score: {game['score']}"
            else:
                response = f"Incorrect. The answer was {game['correct_answer']}. Score: {game['score']}"

            game['current_index'] += 1
            if game['current_index'] == len(questions):
                response += f"\nGame over! You successfully answered {game['score']} out of {len(questions)} questions correctly."
                game['is_game_mode'] = False
            else:
                q = questions[game['current_index']]
                game['current_question'] = q["question"]
                game['correct_answer'] = q["answer"]
                response += f" Next question: {q['question']}"

        # --------------------- Normal AI Chat ---------------------
        else:
            chat_history_ids = user_chat_histories.get(user_id)

            # Encode original input to maintain proper context for DialoGPT
            encoded = tokenizer.encode_plus(
                user_input_original + tokenizer.eos_token,
                return_tensors='pt',
                return_attention_mask=True
            )
            input_ids = encoded['input_ids']
            attention_mask = encoded['attention_mask']

            # Truncate history to prevent OOM errors
            if chat_history_ids is not None:
                if chat_history_ids.shape[-1] > MAX_HISTORY_TOKENS:
                    chat_history_ids = chat_history_ids[:, -MAX_HISTORY_TOKENS:]
                    print(f"[MEMORY] 💾 User {user_id} history truncated to {chat_history_ids.shape[-1]} tokens")

                # Concatenate history with new input
                bot_input_ids = torch.cat([chat_history_ids, input_ids], dim=-1)
                history_attention = torch.ones(chat_history_ids.shape, dtype=torch.long)
                attention_mask = torch.cat([history_attention, attention_mask], dim=-1)
            else:
                bot_input_ids = input_ids

            # Generate response with transformer model
            chat_history_ids = model.generate(
                bot_input_ids,
                attention_mask=attention_mask,
                max_length=1000,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=True,
                top_p=0.95,
                top_k=50,
                temperature=0.75
            )

            # Decode only the new tokens (exclude input)
            response = tokenizer.decode(
                chat_history_ids[:, bot_input_ids.shape[-1]:][0],
                skip_special_tokens=True
            ).strip()

            if not response:
                response = "I'm not sure how to respond to that. Can you rephrase?"

            # Update in-memory chat history
            user_chat_histories[user_id] = chat_history_ids

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
# Speech-to-Text
# =============================================================================
@app.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400

    audio_file = request.files['audio']
    audio_bytes = audio_file.read()

    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm")
        wav_io = io.BytesIO()
        audio.set_frame_rate(16000).set_channels(1).set_sample_width(2).export(wav_io, format="wav")
        wav_data = wav_io.getvalue()

        recognizer = KaldiRecognizer(vosk_model, 16000)
        if not recognizer.AcceptWaveform(wav_data):
            print("Vosk: Partial result, proceeding to final.")

        result = json.loads(recognizer.Result())
        text = result.get("text", "").strip()

        if text:
            return jsonify({'text': text})
        else:
            return jsonify({'error': 'No speech detected'}), 400
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return jsonify({'error': f'Transcription failed: {str(e)}'}), 500

# =============================================================================
# API Endpoints
# =============================================================================
@app.route('/get_reminders', methods=['GET'])
@login_required
def get_reminders():
    user_id = session['user_id']

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute(
        "SELECT label, reminder_time, is_active FROM reminders WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    reminders = [{"label": r[0], "time": r[1], "active": bool(r[2])} for r in c.fetchall()]
    conn.close()

    return jsonify({'reminders': reminders})

@app.route('/get_chat_history', methods=['GET'])
@login_required
def get_chat_history():
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
    print("🤖 Elderly Companion Chatbot - Enhanced Version")
    print(f"[INFO] ✅ Chat history retention: {CHAT_HISTORY_RETENTION_MINUTES} minutes")
    print(f"[INFO] ✅ Max history tokens: {MAX_HISTORY_TOKENS}")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5000, debug=True)