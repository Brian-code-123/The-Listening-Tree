from flask import Flask, render_template, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
from vosk import Model, KaldiRecognizer
import json
from pydub import AudioSegment
import io  # For in-memory processing

app = Flask(__name__)

# Load DialoGPT (unchanged)
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
chat_history_ids = None

# Vosk models (adjust paths if needed)
EN_MODEL_PATH = os.path.join('voice_models', 'vosk-model-small-en-us-0.15')


# Load English model by default (you can add a param to switch languages later)
vosk_model = Model(EN_MODEL_PATH)

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/get_response', methods=['POST'])
# Unchanged - your existing code

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    # No lang check needed; always use English
    vosk_model = Model(EN_MODEL_PATH)  # Or keep the global if you move loading outside

    # Convert WebM/Opus to WAV using pydub (in-memory to avoid temp files)
    audio = AudioSegment.from_file(io.BytesIO(audio_file.read()), format="webm")
    wav_data = audio.set_frame_rate(16000).set_sample_width(2).set_channels(1).export(format="wav").read()

    # Transcribe with Vosk
    rec = KaldiRecognizer(vosk_model, 16000)
    rec.AcceptWaveform(wav_data)
    result = json.loads(rec.Result())

    text = result.get('text', '').strip()
    if not text:
        return jsonify({'error': 'No speech detected'}), 400

    return jsonify({'text': text})

if __name__ == '__main__':
    app.run(debug=True)