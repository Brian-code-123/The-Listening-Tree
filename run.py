from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
from vosk import Model, KaldiRecognizer
import json
from pydub import AudioSegment
import io
import sqlite3
from datetime import datetime
import threading
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Secure random secret key for sessions

# Load models
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
EN_MODEL_PATH = os.path.join('voice_models', 'vosk-model-small-en-us-0.15')
vosk_model = Model(EN_MODEL_PATH)

# Game state (global for simplicity; per-user in production)
is_game_mode = False
current_question = None
correct_answer = None
questions = [
    {"question": "What’s the capital of France?", "answer": "paris"},
    {"question": "What’s 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"}
]
current_index = 0

# SQLite setup
def init_db():
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

# Check reminders in a separate thread
def check_reminders():
    while True:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT user_id, label, time FROM reminders WHERE active = 1")
        reminders = c.fetchall()
        current_time = datetime.now().strftime('%H:%M')
        for user_id, label, time in reminders:
            if time == current_time:
                print(f"Reminder for user {user_id}: {label} at {time}")  # JS handles alert/audio
        conn.close()
        import time; time.sleep(60)

threading.Thread(target=check_reminders, daemon=True).start()

# Authentication decorator
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']  # In production, hash this
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
        else:
            return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('chat.html')

@app.route('/get_response', methods=['POST'])
@login_required
def get_response():
    user_id = session['user_id']
    user_input = request.form['msg'].lower().strip()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Store user message
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
              (user_id, timestamp, 'user', user_input))
    conn.commit()

    if user_input.startswith("set reminder"):
        parts = user_input.split()
        if len(parts) > 3:
            time = parts[-1]
            if len(time) == 5 and time[2] == ':' and time[:2].isdigit() and time[3:].isdigit() and 0 <= int(time[:2]) <= 23 and 0 <= int(time[3:]) <= 59:
                label = ' '.join(parts[2:-1])
                c.execute("INSERT INTO reminders (user_id, label, time, active) VALUES (?, ?, ?, 1)", (user_id, label, time))
                conn.commit()
                response = f"Reminder set for {label} at {time}"
                c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
                          (user_id, timestamp, 'bot', response))
                conn.commit()
                conn.close()
                return jsonify({'response': response})
        response = "Invalid format. Use: set reminder [label] [HH:MM]"
        c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
                  (user_id, timestamp, 'bot', response))
        conn.commit()
        conn.close()
        return jsonify({'response': response})

    if user_input.startswith("delete reminder"):
        parts = user_input.split()
        if len(parts) > 2:
            label = ' '.join(parts[2:])
            c.execute("DELETE FROM reminders WHERE user_id = ? AND label = ? AND active = 1", (user_id, label))
            conn.commit()
            response = f"Deleted reminder for {label}" if c.rowcount > 0 else "No matching reminder found"
            c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
                      (user_id, timestamp, 'bot', response))
            conn.commit()
            conn.close()
            return jsonify({'response': response})
        response = "Invalid format. Use: delete reminder [label]"
        c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
                  (user_id, timestamp, 'bot', response))
        conn.commit()
        conn.close()
        return jsonify({'response': response})

    if user_input.startswith("set preference"):
        parts = user_input.split()
        if len(parts) >= 4:
            key = parts[2]
            value = ' '.join(parts[3:])
            c.execute("INSERT OR REPLACE INTO preferences (user_id, key, value) VALUES (?, ?, ?)", (user_id, key, value))
            conn.commit()
            response = f"Preference set: {key} = {value}"
        else:
            response = "Invalid format. Use: set preference [key] [value]"
        c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
                  (user_id, timestamp, 'bot', response))
        conn.commit()
        conn.close()
        return jsonify({'response': response})

    # Game logic (global state; for multi-user, store per user)
    global is_game_mode, current_question, correct_answer, current_index
    if user_input == "play game" and not is_game_mode:
        is_game_mode = True
        current_index = 0
        current_question = questions[current_index]["question"]
        correct_answer = questions[current_index]["answer"]
        response = f"Let's play a memory game! Here's your first question: {current_question}"
    elif user_input == "exit game" and is_game_mode:
        is_game_mode = False
        current_question = None
        correct_answer = None
        response = "Game ended. Feel free to chat with me!"
    elif is_game_mode:
        if current_question:
            if user_input == correct_answer:
                current_index = (current_index + 1) % len(questions)
                if current_index == 0:
                    is_game_mode = False
                    response = "Great job! You answered all questions correctly. Game over!"
                else:
                    current_question = questions[current_index]["question"]
                    correct_answer = questions[current_index]["answer"]
                    response = f"Correct! Next question: {current_question}"
            else:
                response = f"Nope, that's not it. Try again: {current_question}"
        else:
            is_game_mode = False
            response = "Game error. Returning to chat mode."
    else:
        # Normal chat (global chat_history_ids; per-user needed for production)
        global chat_history_ids
        new_user_input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors='pt')
        bot_input_ids = torch.cat([chat_history_ids, new_user_input_ids], dim=-1) if chat_history_ids is not None else new_user_input_ids
        chat_history_ids = model.generate(
            bot_input_ids,
            max_length=1000,
            pad_token_id=tokenizer.eos_token_id,
            do_sample=True,
            top_p=0.95,
            top_k=50
        )
        response = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)

    # Store bot response
    c.execute("INSERT INTO chat_history (user_id, timestamp, sender, message) VALUES (?, ?, ?, ?)",
              (user_id, timestamp, 'bot', response))
    conn.commit()
    conn.close()
    return jsonify({'response': response})

@app.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    audio = AudioSegment.from_file(io.BytesIO(audio_file.read()), format="webm")
    wav_data = audio.set_frame_rate(16000).set_sample_width(2).set_channels(1).export(format="wav").read()

    rec = KaldiRecognizer(vosk_model, 16000)
    rec.AcceptWaveform(wav_data)
    result = json.loads(rec.Result())

    text = result.get('text', '').strip()
    if not text:
        return jsonify({'error': 'No speech detected'}), 400

    return jsonify({'text': text})

@app.route('/get_reminders', methods=['GET'])
@login_required
def get_reminders():
    user_id = session['user_id']
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT label, time, active FROM reminders WHERE user_id = ? AND active = 1", (user_id,))
    reminders = [{"label": row[0], "time": row[1], "active": bool(row[2])} for row in c.fetchall()]
    conn.close()
    return jsonify({'reminders': reminders})

@app.route('/get_chat_history', methods=['GET'])
@login_required
def get_chat_history():
    user_id = session['user_id']
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT timestamp, sender, message FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,))
    history = [{"timestamp": row[0], "sender": row[1], "message": row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify({'history': history})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)