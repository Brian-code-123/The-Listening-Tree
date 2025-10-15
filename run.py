from flask import Flask, render_template, request, jsonify, session
import os
from datetime import datetime
import uuid
import threading
import time

# 導入 DialoGPT 聊天機器人和語音識別
from dialo_gpt_chatbot import chatbot
from voice_recognition import voice_recognizer

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# 語音狀態管理
voice_status = {
    'is_listening': False,
    'last_result': None,
    'error': None
}

@app.before_request
def make_session_permanent():
    session.permanent = True
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get')
def get_bot_response():
    try:
        user_text = request.args.get('msg')
        user_id = session['user_id']
        
        if not user_text:
            return "請輸入一些內容。"
        
        response = chatbot.get_response(user_text, user_id)
        return response
        
    except Exception as e:
        print(f"錯誤: {e}")
        return "抱歉，我遇到了一些問題。請稍後再試。"

@app.route('/voice/start', methods=['POST'])
def start_voice_recognition():
    """開始語音識別"""
    try:
        if voice_recognizer.is_listening:
            return jsonify({'status': 'already_listening'})
        
        # 在後台線程中啟動語音識別
        def start_voice():
            try:
                voice_recognizer.start_listening()
                voice_status['is_listening'] = True
                voice_status['error'] = None
            except Exception as e:
                voice_status['error'] = str(e)
                print(f"語音啟動錯誤: {e}")
        
        thread = threading.Thread(target=start_voice)
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'started'})
        
    except Exception as e:
        voice_status['error'] = str(e)
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/voice/stop', methods=['POST'])
def stop_voice_recognition():
    """停止語音識別並返回結果"""
    try:
        voice_recognizer.stop_listening()
        voice_status['is_listening'] = False
        
        # 獲取識別結果
        transcript = voice_recognizer.get_current_transcript()
        
        return jsonify({
            'status': 'stopped',
            'transcript': transcript if transcript else ""
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/voice/status', methods=['GET'])
def get_voice_status():
    """獲取語音識別狀態"""
    return jsonify({
        'is_listening': voice_recognizer.is_listening,
        'last_result': voice_recognizer.get_current_transcript(),
        'error': voice_status['error']
    })

@app.route('/voice/devices', methods=['GET'])
def get_audio_devices():
    """獲取可用的音頻設備列表"""
    try:
        devices = voice_recognizer.list_audio_devices()
        return jsonify({'devices': [str(device) for device in devices]})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/profile', methods=['GET', 'POST'])
def user_profile():
    user_id = session['user_id']
    
    if request.method == 'POST':
        user_data = {
            'user_id': user_id,
            'name': request.form.get('name', ''),
            'age': request.form.get('age', 0),
            'medical_conditions': request.form.get('medical_conditions', '').split(','),
            'preferences': request.form.get('preferences', '').split(','),
            'emergency_contact': request.form.get('emergency_contact', '')
        }
        chatbot.update_user_profile(user_data)
        return jsonify({'status': 'success'})
    
    else:
        profile = chatbot.get_user_profile(user_id)
        return jsonify(profile or {})

@app.route('/history')
def conversation_history():
    user_id = session['user_id']
    limit = request.args.get('limit', 10)
    history = chatbot.get_conversation_history(user_id, limit)
    return jsonify(history)

if __name__ == "__main__":
    # 確保必要的目錄存在
    os.makedirs("voice_models", exist_ok=True)
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("voice_logs", exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)