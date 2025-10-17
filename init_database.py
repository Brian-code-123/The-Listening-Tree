from database_manager import db_manager
import json
from datetime import datetime, timedelta

def initialize_sample_data():
    """初始化示例數據"""
    
    # 添加示例用戶
    sample_users = [
        {
            'user_id': 'user_001',
            'username': 'zhang_san',
            'name': '張三',
            'age': 75,
            'gender': '男',
            'medical_conditions': ['高血壓', '糖尿病'],
            'medications': ['降壓藥', '胰島素'],
            'preferences': {'language': 'zh', 'font_size': 'large'},
            'emergency_contact_name': '張小三',
            'emergency_contact_phone': '13800138000',
            'emergency_contact_relation': '兒子'
        },
        {
            'user_id': 'user_002', 
            'username': 'li_si',
            'name': '李四',
            'age': 82,
            'gender': '女',
            'medical_conditions': ['關節炎', '心臟病'],
            'medications': ['止痛藥', '心臟藥'],
            'preferences': {'language': 'zh', 'font_size': 'extra_large'},
            'emergency_contact_name': '李小四',
            'emergency_contact_phone': '13900139000',
            'emergency_contact_relation': '女兒'
        }
    ]
    
    for user in sample_users:
        if db_manager.add_user(user):
            print(f"成功添加用戶: {user['name']}")
        else:
            print(f"添加用戶失敗: {user['name']}")
    
    # 添加示例對話
    sample_conversations = [
        {
            'user_id': 'user_001',
            'session_id': 'session_001',
            'user_message': '你好，今天感覺怎麼樣？',
            'bot_response': '您好！我是您的智能助手，隨時為您服務。',
            'sentiment_label': 'NEUTRAL',
            'sentiment_score': 0.5
        },
        {
            'user_id': 'user_001',
            'session_id': 'session_001', 
            'user_message': '我今天有點頭暈',
            'bot_response': '聽起來您不太舒服。建議您先坐下休息，如果持續頭暈請及時聯繫家人。',
            'sentiment_label': 'NEGATIVE',
            'sentiment_score': 0.3,
            'urgency_level': 1
        }
    ]
    
    for conv in sample_conversations:
        if db_manager.add_conversation(conv):
            print(f"成功添加對話記錄")
        else:
            print(f"添加對話記錄失敗")
    
    # 添加系統設置
    system_settings = [
        ('max_urgency_level', '3', '最大緊急程度'),
        ('alert_check_interval', '300', '警報檢查間隔(秒)'),
        ('default_language', 'zh', '默認語言'),
        ('emergency_contact_required', 'true', '是否需要緊急聯絡人')
    ]
    
    for key, value, description in system_settings:
        if db_manager.set_system_setting(key, value, description):
            print(f"成功設置系統配置: {key}")
        else:
            print(f"設置系統配置失敗: {key}")
    
    print("示例數據初始化完成")

def test_database_operations():
    """測試數據庫操作"""
    print("開始數據庫操作測試...")
    
    # 測試用戶查詢
    user = db_manager.get_user('user_001')
    if user:
        print(f"用戶查詢成功: {user['name']}")
    else:
        print("用戶查詢失敗")
    
    # 測試對話歷史
    conversations = db_manager.get_conversation_history('user_001', 10)
    print(f"獲取到 {len(conversations)} 條對話記錄")
    
    # 測試統計數據
    stats = db_manager.get_user_statistics('user_001')
    print(f"用戶統計: {stats}")
    
    print("數據庫操作測試完成")

if __name__ == "__main__":
    print("開始初始化數據庫...")
    initialize_sample_data()
    test_database_operations()
    print("數據庫初始化完成！")