import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class DatabaseManager:
    def __init__(self, db_path='elderly_chatbot.db'):
        """
        數據庫管理器
        Args:
            db_path: 數據庫文件路徑
        """
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """初始化數據庫連接和表結構"""
        try:
            # 確保目錄存在
            os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)
            
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 使查詢結果可以像字典一樣訪問
            
            # 啟用外鍵約束
            self.conn.execute("PRAGMA foreign_keys = ON")
            
            # 創建所有表
            self._create_tables()
            print("數據庫初始化完成")
            
        except Exception as e:
            print(f"數據庫初始化失敗: {e}")
            raise
    
    def _create_tables(self):
        """創建所有數據表"""
        
        # 用戶表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT CHECK(gender IN ('男', '女', '其他')),
                medical_conditions TEXT,  -- JSON字符串存儲健康狀況
                medications TEXT,         -- JSON字符串存儲用藥信息
                preferences TEXT,         -- JSON字符串存儲用戶偏好
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                emergency_contact_relation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # 對話記錄表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                message_type TEXT DEFAULT 'text' CHECK(message_type IN ('text', 'voice')),
                sentiment_label TEXT,
                sentiment_score REAL,
                urgency_level INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_timestamp (timestamp)
            )
        ''')
        
        # 情感分析記錄表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS sentiment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                sentiment_label TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                emotion_tags TEXT,  -- JSON字符串存儲檢測到的情感
                urgency_level INTEGER DEFAULT 0,
                analysis_method TEXT DEFAULT 'model',  -- model, rule_based, combined
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                INDEX idx_user_sentiment (user_id, sentiment_label)
            )
        ''')
        
        # 情感趨勢表（每日匯總）
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS sentiment_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date DATE NOT NULL,
                total_messages INTEGER DEFAULT 0,
                avg_sentiment_score REAL DEFAULT 0.5,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                urgent_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        
        # 健康數據表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS health_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                data_type TEXT NOT NULL CHECK(data_type IN ('symptom', 'vital', 'medication', 'activity')),
                value TEXT NOT NULL,
                severity INTEGER DEFAULT 0 CHECK(severity >= 0 AND severity <= 10),
                notes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                INDEX idx_user_health (user_id, data_type)
            )
        ''')
        
        # 警報記錄表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                alert_type TEXT NOT NULL CHECK(alert_type IN ('health', 'sentiment', 'system', 'emergency')),
                alert_level TEXT NOT NULL CHECK(alert_level IN ('low', 'medium', 'high', 'critical')),
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_resolved BOOLEAN DEFAULT 0,
                resolved_at TIMESTAMP,
                resolved_by TEXT,  -- system, admin, user
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                INDEX idx_alert_status (is_resolved, alert_level)
            )
        ''')
        
        # 語音記錄表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS voice_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                audio_file_path TEXT,
                transcript_text TEXT,
                confidence_score REAL,
                duration_seconds REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        
        # 系統設置表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        print("所有數據表創建完成")
    
    def add_user(self, user_data: Dict) -> bool:
        """添加新用戶"""
        try:
            required_fields = ['user_id', 'username', 'name']
            for field in required_fields:
                if field not in user_data:
                    raise ValueError(f"缺少必要字段: {field}")
            
            self.conn.execute('''
                INSERT INTO users 
                (user_id, username, name, age, gender, medical_conditions, medications, 
                 preferences, emergency_contact_name, emergency_contact_phone, emergency_contact_relation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['user_id'],
                user_data['username'],
                user_data['name'],
                user_data.get('age'),
                user_data.get('gender'),
                json.dumps(user_data.get('medical_conditions', []), ensure_ascii=False),
                json.dumps(user_data.get('medications', []), ensure_ascii=False),
                json.dumps(user_data.get('preferences', {}), ensure_ascii=False),
                user_data.get('emergency_contact_name'),
                user_data.get('emergency_contact_phone'),
                user_data.get('emergency_contact_relation')
            ))
            
            self.conn.commit()
            return True
            
        except sqlite3.IntegrityError as e:
            print(f"用戶已存在或數據完整性錯誤: {e}")
            return False
        except Exception as e:
            print(f"添加用戶失敗: {e}")
            return False
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """根據用戶ID獲取用戶信息"""
        try:
            cursor = self.conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            
            if row:
                user_dict = dict(row)
                # 解析JSON字段
                for json_field in ['medical_conditions', 'medications', 'preferences']:
                    if user_dict[json_field]:
                        user_dict[json_field] = json.loads(user_dict[json_field])
                    else:
                        user_dict[json_field] = []
                return user_dict
            return None
            
        except Exception as e:
            print(f"獲取用戶信息失敗: {e}")
            return None
    
    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """更新用戶信息"""
        try:
            # 構建更新語句
            set_clause = []
            params = []
            
            for key, value in update_data.items():
                if key in ['medical_conditions', 'medications', 'preferences']:
                    set_clause.append(f"{key} = ?")
                    params.append(json.dumps(value, ensure_ascii=False))
                else:
                    set_clause.append(f"{key} = ?")
                    params.append(value)
            
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(set_clause)} WHERE user_id = ?"
            self.conn.execute(query, params)
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"更新用戶信息失敗: {e}")
            return False
    
    def add_conversation(self, conversation_data: Dict) -> bool:
        """添加對話記錄"""
        try:
            self.conn.execute('''
                INSERT INTO conversations 
                (user_id, session_id, user_message, bot_response, message_type, 
                 sentiment_label, sentiment_score, urgency_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                conversation_data['user_id'],
                conversation_data.get('session_id', 'default'),
                conversation_data['user_message'],
                conversation_data['bot_response'],
                conversation_data.get('message_type', 'text'),
                conversation_data.get('sentiment_label'),
                conversation_data.get('sentiment_score'),
                conversation_data.get('urgency_level', 0)
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"添加對話記錄失敗: {e}")
            return False
    
    def get_conversation_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """獲取用戶對話歷史"""
        try:
            cursor = self.conn.execute('''
                SELECT * FROM conversations 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"獲取對話歷史失敗: {e}")
            return []
    
    def add_sentiment_record(self, sentiment_data: Dict) -> bool:
        """添加情感分析記錄"""
        try:
            self.conn.execute('''
                INSERT INTO sentiment_history 
                (user_id, message, sentiment_label, sentiment_score, emotion_tags, urgency_level, analysis_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                sentiment_data['user_id'],
                sentiment_data['message'],
                sentiment_data['sentiment_label'],
                sentiment_data['sentiment_score'],
                json.dumps(sentiment_data.get('emotion_tags', []), ensure_ascii=False),
                sentiment_data.get('urgency_level', 0),
                sentiment_data.get('analysis_method', 'model')
            ))
            
            self.conn.commit()
            
            # 更新情感趨勢
            self._update_sentiment_trends(sentiment_data['user_id'])
            
            return True
            
        except Exception as e:
            print(f"添加情感分析記錄失敗: {e}")
            return False
    
    def _update_sentiment_trends(self, user_id: str):
        """更新用戶情感趨勢"""
        try:
            today = datetime.now().date()
            
            # 計算今日情感統計
            cursor = self.conn.execute('''
                SELECT 
                    COUNT(*) as total_messages,
                    AVG(sentiment_score) as avg_score,
                    COUNT(CASE WHEN sentiment_label = 'POSITIVE' THEN 1 END) as positive_count,
                    COUNT(CASE WHEN sentiment_label = 'NEGATIVE' THEN 1 END) as negative_count,
                    COUNT(CASE WHEN sentiment_label = 'NEUTRAL' THEN 1 END) as neutral_count,
                    COUNT(CASE WHEN urgency_level >= 2 THEN 1 END) as urgent_count
                FROM sentiment_history 
                WHERE user_id = ? AND DATE(timestamp) = ?
            ''', (user_id, today))
            
            result = cursor.fetchone()
            
            if result:
                self.conn.execute('''
                    INSERT OR REPLACE INTO sentiment_trends 
                    (user_id, date, total_messages, avg_sentiment_score, positive_count, negative_count, neutral_count, urgent_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, today, *result))
                self.conn.commit()
                
        except Exception as e:
            print(f"更新情感趨勢失敗: {e}")
    
    def get_sentiment_trends(self, user_id: str, days: int = 7) -> List[Dict]:
        """獲取用戶情感趨勢"""
        try:
            start_date = (datetime.now() - timedelta(days=days)).date()
            
            cursor = self.conn.execute('''
                SELECT date, total_messages, avg_sentiment_score, positive_count, negative_count, neutral_count, urgent_count
                FROM sentiment_trends 
                WHERE user_id = ? AND date >= ?
                ORDER BY date ASC
            ''', (user_id, start_date))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"獲取情感趨勢失敗: {e}")
            return []
    
    def add_health_data(self, health_data: Dict) -> bool:
        """添加健康數據"""
        try:
            self.conn.execute('''
                INSERT INTO health_data 
                (user_id, data_type, value, severity, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                health_data['user_id'],
                health_data['data_type'],
                health_data['value'],
                health_data.get('severity', 0),
                health_data.get('notes', '')
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"添加健康數據失敗: {e}")
            return False
    
    def add_alert(self, alert_data: Dict) -> bool:
        """添加警報記錄"""
        try:
            self.conn.execute('''
                INSERT INTO alerts 
                (user_id, alert_type, alert_level, title, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                alert_data['user_id'],
                alert_data['alert_type'],
                alert_data['alert_level'],
                alert_data['title'],
                alert_data['message']
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"添加警報失敗: {e}")
            return False
    
    def get_active_alerts(self, user_id: str = None) -> List[Dict]:
        """獲取活動警報"""
        try:
            if user_id:
                cursor = self.conn.execute('''
                    SELECT * FROM alerts 
                    WHERE is_resolved = 0 AND user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
            else:
                cursor = self.conn.execute('''
                    SELECT * FROM alerts 
                    WHERE is_resolved = 0 
                    ORDER BY created_at DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"獲取警報失敗: {e}")
            return []
    
    def resolve_alert(self, alert_id: int, resolved_by: str = "system") -> bool:
        """解決警報"""
        try:
            self.conn.execute('''
                UPDATE alerts 
                SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
                WHERE id = ?
            ''', (resolved_by, alert_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"解決警報失敗: {e}")
            return False
    
    def add_voice_record(self, voice_data: Dict) -> bool:
        """添加語音記錄"""
        try:
            self.conn.execute('''
                INSERT INTO voice_records 
                (user_id, audio_file_path, transcript_text, confidence_score, duration_seconds)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                voice_data['user_id'],
                voice_data.get('audio_file_path'),
                voice_data.get('transcript_text'),
                voice_data.get('confidence_score'),
                voice_data.get('duration_seconds')
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"添加語音記錄失敗: {e}")
            return False
    
    def get_system_setting(self, key: str, default: str = None) -> str:
        """獲取系統設置"""
        try:
            cursor = self.conn.execute(
                'SELECT setting_value FROM system_settings WHERE setting_key = ?', 
                (key,)
            )
            result = cursor.fetchone()
            return result[0] if result else default
        except Exception as e:
            print(f"獲取系統設置失敗: {e}")
            return default
    
    def set_system_setting(self, key: str, value: str, description: str = None) -> bool:
        """設置系統設置"""
        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO system_settings 
                (setting_key, setting_value, description)
                VALUES (?, ?, ?)
            ''', (key, value, description))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"設置系統設置失敗: {e}")
            return False
    
    def get_user_statistics(self, user_id: str) -> Dict:
        """獲取用戶統計數據"""
        try:
            stats = {}
            
            # 總對話數
            cursor = self.conn.execute(
                'SELECT COUNT(*) FROM conversations WHERE user_id = ?', 
                (user_id,)
            )
            stats['total_conversations'] = cursor.fetchone()[0]
            
            # 今日對話數
            cursor = self.conn.execute('''
                SELECT COUNT(*) FROM conversations 
                WHERE user_id = ? AND DATE(timestamp) = DATE('now')
            ''', (user_id,))
            stats['today_conversations'] = cursor.fetchone()[0]
            
            # 平均情感分數
            cursor = self.conn.execute('''
                SELECT AVG(sentiment_score) FROM sentiment_history 
                WHERE user_id = ? AND DATE(timestamp) >= DATE('now', '-7 days')
            ''', (user_id,))
            stats['avg_sentiment_7days'] = cursor.fetchone()[0] or 0.5
            
            # 活動警報數
            cursor = self.conn.execute('''
                SELECT COUNT(*) FROM alerts 
                WHERE user_id = ? AND is_resolved = 0
            ''', (user_id,))
            stats['active_alerts'] = cursor.fetchone()[0]
            
            return stats
            
        except Exception as e:
            print(f"獲取用戶統計失敗: {e}")
            return {}
    
    def close(self):
        """關閉數據庫連接"""
        if self.conn:
            self.conn.close()

# 全局數據庫管理器實例
db_manager = DatabaseManager()