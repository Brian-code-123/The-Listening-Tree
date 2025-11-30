from flask import Flask, render_template, request, jsonify, redirect, url_for, session
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
app.secret_key = secrets.token_hex(16)  # Secure random key for session signing

# =============================================================================
# Global In-Memory State (per user)
# =============================================================================
user_chat_histories = {}  # Stores conversation context (token IDs) per user for DialoGPT
user_game_states = {}     # Tracks quiz game progress per user

# =============================================================================
# Model Loading (DialoGPT for chat, Vosk for offline speech recognition)
# =============================================================================
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Padding token required for generation
tokenizer.pad_token = tokenizer.eos_token

# Load Vosk English model (offline STT)
EN_MODEL_PATH = os.path.join('voice_models', 'vosk-model-small-en-us-0.15')
vosk_model = Model(EN_MODEL_PATH)

# =============================================================================
# Quiz Game Questions (simple memory game)
# =============================================================================
questions = [
    {"question": "What’s the capital of France?", "answer": "paris"},
    {"question": "What’s 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"}
]

# =============================================================================
# Database Initialization
# =============================================================================
def init_db():
    """Create necessary tables if they don't exist."""
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reminders 
                 (id INTEGER PRIMARY KEY, user_id TEXT, label TEXT, time TEXT, active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS preferences 
                 (id INTEGER PRIMARY KEY, user_id TEXT, key TEXT, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (id INTEGER PRIMARY KEY, user_id TEXT, timestamp TEXT, sender TEXT, message TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    conn.commit()
    conn.close()

init_db()

# =============================================================================
# Background Reminder Checker (runs every minute)
# =============================================================================
def check_reminders():
    """Background thread that logs due reminders (actual alert is handled client-side)."""
    while True:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT user_id, label, time FROM reminders WHERE active = 1")
        reminders = c.fetchall()
        current_time = datetime.now().strftime('%H:%M')
        for user_id, label, time in reminders:
            if time == current_time:
                print(f"[REMINDER TRIGGERED] User {user_id}: {label} at {time}")
                # Client-side JS handles actual alert + sound
        conn.close()
        threading.Event().wait(60)  # Sleep 60 seconds

# Start background reminder thread
threading.Thread(target=check_reminders, daemon=True).start()

# =============================================================================
# Authentication Decorator
# =============================================================================
def login_required(f):
    """Redirect unauthenticated users to login page."""
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# =============================================================================
# Routes: Authentication
# =============================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']  # WARNING: In production, hash this!
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            session['user_id'] = username
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Username already exists")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = username
            return redirect(url_for('index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# =============================================================================
# Main Chat Interface
# =============================================================================
@app.route('/')
@login_required
def index():
    return render_template('chat.html')

# =============================================================================
# Core: Get Bot Response + Special Commands
# =============================================================================
@app.route('/get_response', methods=['POST'])
@login_required
def get_response():
    user_id = session['user_id']
    user_input = request.form['msg'].lower().strip()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()

    # Save user message
    c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
              (user_id, timestamp, 'user', user_input))
    conn.commit()

    response = ""

    # --------------------- Reminder Commands ---------------------
    if user_input.startswith("set reminder"):
        parts = user_input.split()
        if len(parts) >= 4 and len(parts[-1]) == 5 and parts[-1][2] == ':':
            time_str = parts[-1]
            label = ' '.join(parts[2:-1])
            try:
                h, m = map(int, time_str.split(':'))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    c.execute("INSERT INTO reminders (user_id, label, time, active) VALUES (?, ?, ?, 1)",
                              (user_id, label, time_str))
                    conn.commit()
                    response = f"Reminder set: {label} at {time_str}"
                else:
                    response = "Invalid time. Use 24-hour format HH:MM"
            except:
                response = "Invalid time format. Use HH:MM"
        else:
            response = "Usage: set reminder [activity] [HH:MM]"

    elif user_input.startswith("delete reminder"):
        parts = user_input.split(maxsplit=2)
        if len(parts) == 3:
            label = parts[2]
            c.execute("DELETE FROM reminders WHERE user_id = ? AND label = ? AND active = 1", (user_id, label))
            if c.rowcount > 0:
                response = f"Deleted reminder: {label}"
            else:
                response = "No active reminder found with that name."
            conn.commit()
        else:
            response = "Usage: delete reminder [activity]"

    # --------------------- Preferences ---------------------
    elif user_input.startswith("set preference"):
        parts = user_input.split(maxsplit=4)
        if len(parts) >= 4:
            key, value = parts[2], parts[3]
            c.execute("INSERT OR REPLACE INTO preferences (user_id, key, value) VALUES (?, ?, ?)",
                      (user_id, key, value))
            conn.commit()
            response = f"Preference updated: {key} = {value}"
        else:
            response = "Usage: set preference [key] [value]"

    # --------------------- Quiz Game Mode ---------------------
    else:
        game = user_game_states.setdefault(user_id, {
            'is_game_mode': False, 'current_index': 0,
            'current_question': None, 'correct_answer': None
        })

        if user_input == "play game" and not game['is_game_mode']:
            game['is_game_mode'] = True
            game['current_index'] = 0
            game['current_question'] = questions[0]["question"]
            game['correct_answer'] = questions[0]["answer"]
            response = f"Let's play! First question: {game['current_question']}"

        elif user_input == "exit game" and game['is_game_mode']:
            game['is_game_mode'] = False
            response = "Game stopped. Back to normal chat!"

        elif game['is_game_mode']:
            if user_input.strip() == game['correct_answer']:
                game['current_index'] = (game['current_index'] + 1) % len(questions)
                if game['current_index'] == 0:
                    game['is_game_mode'] = False
                    response = "Amazing! You completed the game!"
                else:
                    q = questions[game['current_index']]
                    game['current_question'] = q["question"]
                    game['correct_answer'] = q["answer"]
                    response = f"Correct! Next: {q['question']}"
            else:
                response = f"Not quite. Try again: {game['current_question']}"

        # --------------------- Normal Conversational AI ---------------------
        else:
            chat_history_ids = user_chat_histories.get(user_id)
            input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors='pt')
            bot_input_ids = torch.cat([chat_history_ids, input_ids], dim=-1) if chat_history_ids is not None else input_ids

            # Generate response with sampling for more natural replies
            chat_history_ids = model.generate(
                bot_input_ids,
                max_length=1000,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=True,
                top_p=0.95,
                top_k=50,
                temperature=0.75
            )
            response = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)
            user_chat_histories[user_id] = chat_history_ids  # Update context

    # Save bot response
    c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
              (user_id, timestamp, 'bot', response))
    conn.commit()
    conn.close()

    return jsonify({'response': response})

# =============================================================================
# Speech-to-Text (Offline using Vosk)
# =============================================================================
@app.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400

    audio_file = request.files['audio']
    audio_bytes = audio_file.read()

    # Convert webm → wav in memory
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="webm")
    wav_io = io.BytesIO()
    audio.set_frame_rate(16000).set_channels(1).set_sample_width(2).export(wav_io, format="wav")
    wav_data = wav_io.getvalue()

    recognizer = KaldiRecognizer(vosk_model, 16000)
    recognizer.AcceptWaveform(wav_data)
    result = json.loads(recognizer.Result())

    text = result.get("text", "").strip()
    return jsonify({'text': text}) if text else jsonify({'error': 'No speech detected'}), 400

# =============================================================================
# API Endpoints for Frontend
# =============================================================================
@app.route('/get_reminders', methods=['GET'])
@login_required
def get_reminders():
    user_id = session['user_id']
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT label, time FROM reminders WHERE user_id = ? AND active = 1", (user_id,))
    reminders = [{"label": r[0], "time": r[1], "active": True} for r in c.fetchall()]
    conn.close()
    return jsonify({'reminders': reminders})

@app.route('/get_chat_history', methods=['GET'])
@login_required
def get_chat_history():
    user_id = session['user_id']
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT timestamp, sender, message FROM chat_history WHERE user_id = ? ORDER BY timestamp", (user_id,))
    history = [{"timestamp": r[0], "sender": r[1], "message": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify({'history': history})

# =============================================================================
# Run Server
# =============================================================================
if __name__ == '__main__':
    print("Elderly Companion Chatbot is running...")
    app.run(host='0.0.0.0', port=5000, debug=True)