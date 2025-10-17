from flask import Flask, render_template, request, jsonify, session
import os
from datetime import datetime
import uuid
import threading

# 導入統一的數據庫管理器和各功能模塊
from database_manager import db_manager
from dialo_gpt_chatbot import chatbot
from voice_recognition import voice_recognizer
from sentiment_analyzer import sentiment_analyzer

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# 初始化數據庫（可選，如果需要重置數據庫可以取消注釋）
# from init_database import initialize_sample_data
# initialize_sample_data()

@app.before_request
def make_session_permanent():
    """為每個用戶創建會話"""
    session.permanent = True
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get')
def get_bot_response():
    """獲取聊天機器人回應（集成情感分析）"""
    try:
        user_text = request.args.get('msg')
        user_id = session['user_id']
        session_id = session['session_id']
        
        if not user_text:
            return "請輸入一些內容。"
        
        # 1. 進行情感分析
        sentiment_result = sentiment_analyzer.analyze_sentiment(user_text, user_id)
        
        # 2. 根據情感結果生成回應
        response = _get_empathetic_response(user_text, sentiment_result, user_id, session_id)
        
        return response
        
    except Exception as e:
        print(f"對話處理錯誤: {e}")
        return "抱歉，我遇到了一些問題。請稍後再試。"

def _get_empathetic_response(user_text: str, sentiment: Dict, user_id: str, session_id: str) -> str:
    """根據情感分析生成更有同理心的回應"""
    
    # 處理緊急情況
    if sentiment['urgency_level'] >= 3:
        emergency_response = _handle_emergency_situation(sentiment, user_id)
        if emergency_response:
            return emergency_response
    
    # 使用 DialoGPT 生成基礎回應
    base_response = chatbot.get_response(user_text, user_id, session_id)
    
    # 根據情感調整回應
    adjusted_response = _adjust_response_by_sentiment(base_response, sentiment)
    
    return adjusted_response

def _handle_emergency_situation(sentiment: Dict, user_id: str) -> str:
    """處理緊急情況"""
    if sentiment['urgency_level'] >= 3:
        # 創建緊急警報
        alert_data = {
            'user_id': user_id,
            'alert_type': 'emergency',
            'alert_level': 'critical',
            'title': '檢測到緊急情況',
            'message': f'用戶表達了緊急需求: {sentiment.get("emotions", [])}'
        }
        db_manager.add_alert(alert_data)
        
        return (f"⚠️ 緊急情況！建議您立即聯繫家人或撥打急救電話。"
                f"同時，我建議：{sentiment['recommendation']}")
    
    return ""

def _adjust_response_by_sentiment(response: str, sentiment: Dict) -> str:
    """根據情感調整回應語氣"""
    if sentiment['label'] == 'NEGATIVE' and sentiment['score'] > 0.6:
        comforting_prefixes = ["我理解您的心情，", "聽起來您很不容易，", "我能感受到您的難過，"]
        import random
        prefix = random.choice(comforting_prefixes)
        return prefix + response
    
    elif sentiment['label'] == 'POSITIVE' and sentiment['score'] > 0.7:
        celebrating_suffixes = [" 真為您感到高興！", " 這真是太棒了！", " 聽到這個消息我很開心！"]
        import random
        suffix = random.choice(celebrating_suffixes)
        return response + suffix
    
    return response

# 用戶管理路由
@app.route('/user/register', methods=['POST'])
def register_user():
    """用戶註冊"""
    try:
        user_data = {
            'user_id': str(uuid.uuid4()),
            'username': request.json.get('username'),
            'name': request.json.get('name'),
            'age': request.json.get('age'),
            'gender': request.json.get('gender'),
            'medical_conditions': request.json.get('medical_conditions', []),
            'medications': request.json.get('medications', []),
            'preferences': request.json.get('preferences', {}),
            'emergency_contact_name': request.json.get('emergency_contact_name'),
            'emergency_contact_phone': request.json.get('emergency_contact_phone'),
            'emergency_contact_relation': request.json.get('emergency_contact_relation')
        }
        
        if db_manager.add_user(user_data):
            return jsonify({'status': 'success', 'user_id': user_data['user_id']})
        else:
            return jsonify({'status': 'error', 'message': '用戶註冊失敗'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    """用戶資料管理"""
    user_id = session['user_id']
    
    if request.method == 'POST':
        update_data = request.json
        if db_manager.update_user(user_id, update_data):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': '更新失敗'})
    
    else:
        profile = db_manager.get_user(user_id)
        if profile:
            return jsonify(profile)
        else:
            return jsonify({'status': 'error', 'message': '用戶不存在'})

# 數據查詢路由
@app.route('/conversations/history')
def get_conversation_history():
    """獲取對話歷史"""
    user_id = session['user_id']
    limit = request.args.get('limit', 50, type=int)
    
    conversations = db_manager.get_conversation_history(user_id, limit)
    return jsonify({'conversations': conversations})

@app.route('/sentiment/trends')
def get_sentiment_trends():
    """獲取情感趨勢"""
    user_id = session['user_id']
    days = request.args.get('days', 7, type=int)
    
    trends = db_manager.get_sentiment_trends(user_id, days)
    return jsonify({'trends': trends})

@app.route('/alerts/active')
def get_active_alerts():
    """獲取活動警報"""
    user_id = session['user_id']
    alerts = db_manager.get_active_alerts(user_id)
    return jsonify({'alerts': alerts})

@app.route('/stats/user')
def get_user_stats():
    """獲取用戶統計"""
    user_id = session['user_id']
    stats = db_manager.get_user_statistics(user_id)
    return jsonify(stats)

# 語音路由（保持不變）
@app.route('/voice/start', methods=['POST'])
def start_voice_recognition():
    # 現有代碼...
    pass

@app.route('/voice/stop', methods=['POST'])
def stop_voice_recognition():
    # 現有代碼...
    pass

if __name__ == "__main__":
    # 確保必要的目錄存在
    os.makedirs("voice_models", exist_ok=True)
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("voice_logs", exist_ok=True)
    
    print("啟動老年人聊天助手服務...")
    print(f"數據庫文件: {db_manager.db_path}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)