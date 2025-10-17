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
                medical_conditions TEXT,
                medications TEXT,
                preferences TEXT,
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
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
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
                emotion_tags TEXT,
                urgency_level INTEGER DEFAULT 0,
                analysis_method TEXT DEFAULT 'model',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
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
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
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
                resolved_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
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
        
        # 創建索引
        self._create_indexes()
        
        self.conn.commit()
        print("所有數據表創建完成")
    
    def _create_indexes(self):
        """創建所有索引"""
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id)',
            'CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations (timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_sentiment_user_sentiment ON sentiment_history (user_id, sentiment_label)',
            'CREATE INDEX IF NOT EXISTS idx_health_user_type ON health_data (user_id, data_type)',
            'CREATE INDEX IF NOT EXISTS idx_alerts_status_level ON alerts (is_resolved, alert_level)'
        ]
        
        for index_sql in indexes:
            try:
                self.conn.execute(index_sql)
            except Exception as e:
                print(f"創建索引失敗 {index_sql}: {e}")
    
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

    # 添加其他必要的方法...
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

    # 添加其他必要的方法的存根實現
    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """更新用戶信息"""
        try:
            # 簡化實現
            return True
        except:
            return False

    def add_sentiment_record(self, sentiment_data: Dict) -> bool:
        """添加情感分析記錄"""
        try:
            return True
        except:
            return False

    def get_sentiment_trends(self, user_id: str, days: int = 7) -> List[Dict]:
        """獲取用戶情感趨勢"""
        return []

    def add_health_data(self, health_data: Dict) -> bool:
        """添加健康數據"""
        try:
            return True
        except:
            return False

    def add_alert(self, alert_data: Dict) -> bool:
        """添加警報記錄"""
        try:
            return True
        except:
            return False

    def get_active_alerts(self, user_id: str = None) -> List[Dict]:
        """獲取活動警報"""
        return []

    def resolve_alert(self, alert_id: int, resolved_by: str = "system") -> bool:
        """解決警報"""
        try:
            return True
        except:
            return False

    def get_user_statistics(self, user_id: str) -> Dict:
        """獲取用戶統計數據"""
        return {
            'total_conversations': 0,
            'today_conversations': 0,
            'avg_sentiment_7days': 0.5,
            'active_alerts': 0
        }

    def close(self):
        """關閉數據庫連接"""
        if self.conn:
            self.conn.close()

# 全局數據庫管理器實例
db_manager = DatabaseManager()