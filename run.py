from flask import Flask, render_template, request, jsonify
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
from playsound import playsound

app = Flask(__name__)

# Load models
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
chat_history_ids = None
EN_MODEL_PATH = os.path.join('voice_models', 'vosk-model-small-en-us-0.15')
vosk_model = Model(EN_MODEL_PATH)

# Game state
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
                 (id INTEGER PRIMARY KEY, label TEXT, time TEXT, active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS preferences 
                 (id INTEGER PRIMARY KEY, user_id TEXT, key TEXT, value TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Check reminders in a separate thread
def check_reminders():
    while True:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT label, time FROM reminders WHERE active = 1")
        reminders = c.fetchall()
        current_time = datetime.now().strftime('%H:%M')
        for label, time in reminders:
            if time == current_time:
                print(f"Reminder: {label} at {time}")  # JS handles alert/audio
        conn.close()
        import time; time.sleep(60)

threading.Thread(target=check_reminders, daemon=True).start()

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/get_response', methods=['POST'])
def get_response():
    global chat_history_ids, is_game_mode, current_question, correct_answer, current_index
    user_input = request.form['msg'].lower().strip()

    if user_input == "play game" and not is_game_mode:
        is_game_mode = True
        current_index = 0
        current_question = questions[current_index]["question"]
        correct_answer = questions[current_index]["answer"]
        return jsonify({'response': f"Let's play a memory game! Here's your first question: {current_question}"})
    
    elif user_input == "exit game" and is_game_mode:
        is_game_mode = False
        current_question = None
        correct_answer = None
        return jsonify({'response': "Game ended. Feel free to chat with me!"})
    
    elif is_game_mode:
        if current_question:
            if user_input == correct_answer:
                current_index = (current_index + 1) % len(questions)
                if current_index == 0:
                    is_game_mode = False
                    return jsonify({'response': "Great job! You answered all questions correctly. Game over!"})
                current_question = questions[current_index]["question"]
                correct_answer = questions[current_index]["answer"]
                return jsonify({'response': f"Correct! Next question: {current_question}"})
            else:
                return jsonify({'response': f"Nope, that's not it. Try again: {current_question}"})
        else:
            is_game_mode = False
            return jsonify({'response': "Game error. Returning to chat mode."})

    if user_input.startswith("set reminder"):
        parts = user_input.split()
        if len(parts) > 3:
            time = parts[-1]
            if len(time) == 5 and time[2] == ':' and time[:2].isdigit() and time[3:].isdigit() and 0 <= int(time[:2]) <= 23 and 0 <= int(time[3:]) <= 59:
                label = ' '.join(parts[2:-1])
                conn = sqlite3.connect('reminders.db')
                c = conn.cursor()
                c.execute("INSERT INTO reminders (label, time, active) VALUES (?, ?, 1)", (label, time))
                conn.commit()
                conn.close()
                return jsonify({'response': f"Reminder set for {label} at {time}"})
        return jsonify({'response': "Invalid format. Use: set reminder [label] [HH:MM] (e.g., set reminder walk 14:00)"})

    if user_input.startswith("delete reminder"):
        parts = user_input.split()
        if len(parts) > 2:
            label = ' '.join(parts[2:])
            conn = sqlite3.connect('reminders.db')
            c = conn.cursor()
            c.execute("DELETE FROM reminders WHERE label = ? AND active = 1", (label,))
            conn.commit()
            conn.close()
            return jsonify({'response': f"Deleted reminder for {label}" if c.rowcount > 0 else "No matching reminder found"})
        return jsonify({'response': "Invalid format. Use: delete reminder [label] (e.g., delete reminder walk)"})

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
    bot_response = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)
    return jsonify({'response': bot_response})

@app.route('/transcribe', methods=['POST'])
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
def get_reminders():
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT label, time, active FROM reminders WHERE active = 1")
    reminders = [{"label": row[0], "time": row[1], "active": bool(row[2])} for row in c.fetchall()]
    conn.close()
    return jsonify({'reminders': reminders})

if __name__ == '__main__':
    app.run(debug=True)