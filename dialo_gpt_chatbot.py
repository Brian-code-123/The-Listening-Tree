import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import sqlite3
import json
from datetime import datetime

class DialoGPTChatbot:
    def __init__(self, model_name="microsoft/DialoGPT-medium"):
        """
        初始化 DialoGPT 模型
        - small: 快速但質量一般
        - medium: 平衡性能與質量 (推薦)
        - large: 質量最好但資源消耗大
        """
        print("加載 DialoGPT 模型中...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.chat_history_ids = None
        self.setup_database()
        
    def setup_database(self):
        """初始化 SQLite 數據庫"""
        self.conn = sqlite3.connect('elderly_chatbot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        """創建數據庫表"""
        # 用戶表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                name TEXT,
                age INTEGER,
                medical_conditions TEXT,
                preferences TEXT,
                emergency_contact TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 對話歷史表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                user_message TEXT,
                bot_response TEXT,
                sentiment_score REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 健康數據表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS health_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                symptom TEXT,
                severity INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        self.conn.commit()
    
    def get_response(self, user_input, user_id="default_user", step=0):
        """
        生成對話回應
        Args:
            user_input: 用戶輸入
            user_id: 用戶ID
            step: 對話步數 (用於管理上下文長度)
        """
        try:
            # 編碼用戶輸入
            new_user_input_ids = self.tokenizer.encode(
                user_input + self.tokenizer.eos_token, 
                return_tensors='pt'
            )
            
            # 組合對話歷史
            if self.chat_history_ids is not None:
                bot_input_ids = torch.cat([self.chat_history_ids, new_user_input_ids], dim=-1)
            else:
                bot_input_ids = new_user_input_ids
            
            # 生成回應 (添加多樣性參數)
            self.chat_history_ids = self.model.generate(
                bot_input_ids,
                max_length=1000,
                pad_token_id=self.tokenizer.eos_token_id,
                no_repeat_ngram_size=3,
                do_sample=True,
                top_k=50,
                top_p=0.95,
                temperature=0.7
            )
            
            # 解碼回應
            response = self.tokenizer.decode(
                self.chat_history_ids[:, bot_input_ids.shape[-1]:][0], 
                skip_special_tokens=True
            )
            
            # 保存對話到數據庫
            self.save_conversation(user_id, user_input, response)
            
            return response
            
        except Exception as e:
            print(f"對話生成錯誤: {e}")
            return "我遇到了一些技術問題，請稍後再試。"
    
    def save_conversation(self, user_id, user_message, bot_response):
        """保存對話到數據庫"""
        try:
            # 簡單情感分析 (可後續增強)
            sentiment = self.analyze_sentiment(user_message)
            
            self.conn.execute('''
                INSERT INTO conversations (user_id, user_message, bot_response, sentiment_score)
                VALUES (?, ?, ?, ?)
            ''', (user_id, user_message, bot_response, sentiment))
            self.conn.commit()
        except Exception as e:
            print(f"保存對話錯誤: {e}")
    
    def analyze_sentiment(self, text):
        """簡單情感分析 (後續可集成專業庫)"""
        positive_words = ['開心', '高興', '很好', '謝謝', '愛', '喜歡', '美好']
        negative_words = ['難過', '孤獨', '痛苦', '害怕', '擔心', '不舒服']
        
        score = 0.5  # 中性
        if any(word in text for word in positive_words):
            score = 0.8
        elif any(word in text for word in negative_words):
            score = 0.2
            
        return score
    
    def get_user_profile(self, user_id):
        """獲取用戶資料"""
        cursor = self.conn.execute(
            'SELECT * FROM users WHERE user_id = ?', (user_id,)
        )
        return cursor.fetchone()
    
    def update_user_profile(self, user_data):
        """更新用戶資料"""
        self.conn.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, name, age, medical_conditions, preferences, emergency_contact)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_data['user_id'],
            user_data['name'],
            user_data['age'],
            json.dumps(user_data['medical_conditions']),
            json.dumps(user_data['preferences']),
            user_data['emergency_contact']
        ))
        self.conn.commit()
    
    def get_conversation_history(self, user_id, limit=10):
        """獲取對話歷史"""
        cursor = self.conn.execute('''
            SELECT user_message, bot_response, timestamp 
            FROM conversations 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        return cursor.fetchall()

# 全局聊天機器人實例
chatbot = DialoGPTChatbot()