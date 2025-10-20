from flask import Flask, render_template, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
from vosk import Model, KaldiRecognizer
import json
from pydub import AudioSegment
import io  # For in-memory processing

app = Flask(__name__)

# Load DialoGPT
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
chat_history_ids = None

# Vosk models
EN_MODEL_PATH = os.path.join('voice_models', 'vosk-model-small-en-us-0.15')
vosk_model = Model(EN_MODEL_PATH)

# Game state and questions
is_game_mode = False
current_question = None
correct_answer = None
questions = [
    {"question": "What’s the capital of France?", "answer": "paris"},
    {"question": "What’s 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"}
]
current_index = 0

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/get_response', methods=['POST'])
def get_response():
    global chat_history_ids, is_game_mode, current_question, correct_answer, current_index
    user_input = request.form['msg'].lower().strip()

    # Game mode handling
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
                return jsonify({'response': f"Nope, that's not it. Try again: {current_question} (Hint: The answer is {correct_answer})"})
        else:
            is_game_mode = False
            return jsonify({'response': "Game error. Returning to chat mode."})

    # Normal chat mode
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
    vosk_model = Model(EN_MODEL_PATH)  # Reload each time (or move to global for efficiency)

    audio = AudioSegment.from_file(io.BytesIO(audio_file.read()), format="webm")
    wav_data = audio.set_frame_rate(16000).set_sample_width(2).set_channels(1).export(format="wav").read()

    rec = KaldiRecognizer(vosk_model, 16000)
    rec.AcceptWaveform(wav_data)
    result = json.loads(rec.Result())

    text = result.get('text', '').strip()
    if not text:
        return jsonify({'error': 'No speech detected'}), 400

    return jsonify({'text': text})

if __name__ == '__main__':
    app.run(debug=True)