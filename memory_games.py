import sqlite3
import json
import random
from datetime import datetime
from database_manager import db_manager
import logging

class MemoryGameSystem:
    def __init__(self):
        """初始化記憶力遊戲系統"""
        self.logger = self._setup_logging()
        
        # 初始化數據庫表
        self._create_game_tables()
        
        # 預設遊戲題庫
        self.question_banks = {
            'capital_cities': self._load_capital_questions(),
            'simple_math': self._load_math_questions(),
            'memory_sequence': self._load_sequence_questions(),
            'word_memory': self._load_word_questions()
        }
    
    def _setup_logging(self):
        """設置日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('memory_games.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    def _create_game_tables(self):
        """創建遊戲相關數據表"""
        try:
            # 遊戲記錄表
            db_manager.conn.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    total_questions INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    duration_seconds INTEGER DEFAULT 0,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            # 遊戲題目記錄表
            db_manager.conn.execute('''
                CREATE TABLE IF NOT EXISTS game_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_session_id INTEGER,
                    question_text TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    user_answer TEXT,
                    is_correct BOOLEAN DEFAULT 0,
                    question_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_session_id) REFERENCES game_sessions (id) ON DELETE CASCADE
                )
            ''')
            
            # 用戶遊戲統計表
            db_manager.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_game_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    game_type TEXT NOT NULL,
                    total_games INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    best_score INTEGER DEFAULT 0,
                    average_score REAL DEFAULT 0,
                    last_played TIMESTAMP,
                    UNIQUE(user_id, game_type),
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            db_manager.conn.commit()
            self.logger.info("遊戲系統數據表創建完成")
            
        except Exception as e:
            self.logger.error(f"創建遊戲表失敗: {e}")
    
    def _load_capital_questions(self):
        """加載首都城市問題"""
        return [
            {
                'question': '法國的首都是哪裡？',
                'answer': '巴黎',
                'options': ['倫敦', '巴黎', '柏林', '羅馬']
            },
            {
                'question': '日本的首都是哪裡？',
                'answer': '東京',
                'options': ['大阪', '京都', '東京', '名古屋']
            },
            {
                'question': '澳大利亞的首都是哪裡？',
                'answer': '坎培拉',
                'options': ['悉尼', '墨爾本', '坎培拉', '布里斯本']
            },
            {
                'question': '巴西的首都是哪裡？',
                'answer': '巴西利亞',
                'options': ['里約熱內盧', '聖保羅', '巴西利亞', '薩爾瓦多']
            },
            {
                'question': '加拿大的首都是哪裡？',
                'answer': '渥太華',
                'options': ['多倫多', '溫哥華', '蒙特利爾', '渥太華']
            },
            {
                'question': '德國的首都是哪裡？',
                'answer': '柏林',
                'options': ['慕尼黑', '漢堡', '法蘭克福', '柏林']
            },
            {
                'question': '意大利的首都是哪裡？',
                'answer': '羅馬',
                'options': ['米蘭', '佛羅倫斯', '威尼斯', '羅馬']
            },
            {
                'question': '俄羅斯的首都是哪裡？',
                'answer': '莫斯科',
                'options': ['聖彼得堡', '莫斯科', '喀山', '索契']
            }
        ]
    
    def _load_math_questions(self):
        """加載簡單數學問題"""
        questions = []
        for i in range(20):
            a = random.randint(1, 20)
            b = random.randint(1, 20)
            operation = random.choice(['+', '-'])
            
            if operation == '+':
                answer = a + b
                question = f'{a} + {b} = ?'
            else:
                # 確保結果為正數
                a, b = max(a, b), min(a, b)
                answer = a - b
                question = f'{a} - {b} = ?'
            
            # 生成錯誤選項
            options = [answer]
            while len(options) < 4:
                wrong = answer + random.choice([-3, -2, -1, 1, 2, 3])
                if wrong > 0 and wrong not in options:
                    options.append(wrong)
            
            random.shuffle(options)
            
            questions.append({
                'question': question,
                'answer': str(answer),
                'options': [str(opt) for opt in options]
            })
        
        return questions
    
    def _load_sequence_questions(self):
        """加載序列記憶問題"""
        sequences = [
            {'sequence': [2, 4, 6, 8], 'next': 10},
            {'sequence': [1, 3, 5, 7], 'next': 9},
            {'sequence': [5, 10, 15, 20], 'next': 25},
            {'sequence': [3, 6, 9, 12], 'next': 15},
            {'sequence': [1, 2, 4, 8], 'next': 16},
            {'sequence': [10, 9, 8, 7], 'next': 6},
            {'sequence': [2, 3, 5, 8], 'next': 13},
            {'sequence': [1, 4, 9, 16], 'next': 25}
        ]
        
        questions = []
        for seq in sequences:
            sequence_str = ', '.join(map(str, seq['sequence']))
            question = f'觀察這個數字序列：{sequence_str}，下一個數字是什麼？'
            
            # 生成選項
            options = [seq['next']]
            while len(options) < 4:
                wrong = seq['next'] + random.choice([-5, -3, -2, 2, 3, 5])
                if wrong > 0 and wrong not in options:
                    options.append(wrong)
            
            random.shuffle(options)
            
            questions.append({
                'question': question,
                'answer': str(seq['next']),
                'options': [str(opt) for opt in options]
            })
        
        return questions
    
    def _load_word_questions(self):
        """加載單詞記憶問題"""
        word_pairs = [
            {'words': ['蘋果', '香蕉', '橙子'], 'missing': '葡萄'},
            {'words': ['貓', '狗', '鳥'], 'missing': '魚'},
            {'words': ['紅色', '藍色', '綠色'], 'missing': '黃色'},
            {'words': ['春天', '夏天', '秋天'], 'missing': '冬天'},
            {'words': ['北京', '上海', '廣州'], 'missing': '深圳'},
            {'words': ['鋼琴', '小提琴', '吉他'], 'missing': '鼓'},
            {'words': ['醫生', '老師', '工程師'], 'missing': '護士'},
            {'words': ['米飯', '麵條', '餃子'], 'missing': '包子'}
        ]
        
        questions = []
        for pair in word_pairs:
            words_str = '、'.join(pair['words'])
            question = f'記住這些詞：{words_str}。現在缺少哪個相關的詞？'
            
            # 生成選項
            options = [pair['missing']]
            related_words = {
                '蘋果': ['梨子', '桃子', '西瓜'],
                '貓': ['兔子', '老鼠', '烏龜'],
                '紅色': ['紫色', '橙色', '粉色'],
                '春天': ['清晨', '正午', '傍晚'],
                '北京': ['天津', '重慶', '成都'],
                '鋼琴': ['口琴', '笛子', '喇叭'],
                '醫生': ['警察', '司機', '廚師'],
                '米飯': ['饅頭', '麵包', '餅乾']
            }
            
            while len(options) < 4:
                wrong = random.choice(related_words.get(pair['words'][0], ['選項1', '選項2', '選項3']))
                if wrong not in options:
                    options.append(wrong)
            
            random.shuffle(options)
            
            questions.append({
                'question': question,
                'answer': pair['missing'],
                'options': options
            })
        
        return questions
    
    def start_game_session(self, user_id, game_type, question_count=5):
        """開始新的遊戲會話"""
        try:
            # 創建遊戲會話
            cursor = db_manager.conn.execute('''
                INSERT INTO game_sessions (user_id, game_type, total_questions)
                VALUES (?, ?, ?)
            ''', (user_id, game_type, question_count))
            
            session_id = cursor.lastrowid
            db_manager.conn.commit()
            
            # 獲取問題
            questions = self._get_questions(game_type, question_count)
            
            self.logger.info(f"用戶 {user_id} 開始 {game_type} 遊戲，會話ID: {session_id}")
            
            return {
                'session_id': session_id,
                'questions': questions,
                'total_questions': question_count
            }
            
        except Exception as e:
            self.logger.error(f"開始遊戲會話失敗: {e}")
            return None
    
    def _get_questions(self, game_type, count):
        """獲取指定數量的問題"""
        if game_type not in self.question_banks:
            return []
        
        bank = self.question_banks[game_type]
        if count > len(bank):
            count = len(bank)
        
        return random.sample(bank, count)
    
    def submit_answer(self, session_id, question_index, user_answer):
        """提交答案"""
        try:
            # 這裡需要根據實際問題結構來判斷答案
            # 簡化處理：假設問題已經在會話中存儲
            is_correct = False  # 需要實際判斷邏輯
            
            db_manager.conn.execute('''
                INSERT INTO game_questions 
                (game_session_id, question_text, correct_answer, user_answer, is_correct)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, f"Question {question_index}", "correct_answer", user_answer, is_correct))
            
            db_manager.conn.commit()
            
            return {'correct': is_correct, 'correct_answer': "correct_answer"}
            
        except Exception as e:
            self.logger.error(f"提交答案失敗: {e}")
            return None
    
    def end_game_session(self, session_id, score, correct_answers, duration):
        """結束遊戲會話並更新統計"""
        try:
            # 更新遊戲會話
            db_manager.conn.execute('''
                UPDATE game_sessions 
                SET score = ?, correct_answers = ?, duration_seconds = ?
                WHERE id = ?
            ''', (score, correct_answers, duration, session_id))
            
            # 獲取會話信息
            cursor = db_manager.conn.execute('''
                SELECT user_id, game_type FROM game_sessions WHERE id = ?
            ''', (session_id,))
            session_info = cursor.fetchone()
            
            if session_info:
                user_id, game_type = session_info
                
                # 更新用戶遊戲統計
                self._update_user_stats(user_id, game_type, score)
            
            db_manager.conn.commit()
            
            self.logger.info(f"遊戲會話 {session_id} 結束，得分: {score}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"結束遊戲會話失敗: {e}")
            return False
    
    def _update_user_stats(self, user_id, game_type, score):
        """更新用戶遊戲統計"""
        try:
            # 檢查是否已有統計記錄
            cursor = db_manager.conn.execute('''
                SELECT * FROM user_game_stats 
                WHERE user_id = ? AND game_type = ?
            ''', (user_id, game_type))
            
            existing = cursor.fetchone()
            
            if existing:
                # 更新現有記錄
                current_stats = dict(existing)
                total_games = current_stats['total_games'] + 1
                total_score = current_stats['total_score'] + score
                best_score = max(current_stats['best_score'], score)
                average_score = total_score / total_games
                
                db_manager.conn.execute('''
                    UPDATE user_game_stats 
                    SET total_games = ?, total_score = ?, best_score = ?, average_score = ?, last_played = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND game_type = ?
                ''', (total_games, total_score, best_score, average_score, user_id, game_type))
            else:
                # 創建新記錄
                db_manager.conn.execute('''
                    INSERT INTO user_game_stats 
                    (user_id, game_type, total_games, total_score, best_score, average_score, last_played)
                    VALUES (?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, game_type, score, score, score))
            
        except Exception as e:
            self.logger.error(f"更新用戶統計失敗: {e}")
    
    def get_user_stats(self, user_id):
        """獲取用戶遊戲統計"""
        try:
            cursor = db_manager.conn.execute('''
                SELECT * FROM user_game_stats 
                WHERE user_id = ?
                ORDER BY last_played DESC
            ''', (user_id,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            self.logger.error(f"獲取用戶統計失敗: {e}")
            return []
    
    def get_game_history(self, user_id, limit=10):
        """獲取用戶遊戲歷史"""
        try:
            cursor = db_manager.conn.execute('''
                SELECT * FROM game_sessions 
                WHERE user_id = ? 
                ORDER BY played_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            self.logger.error(f"獲取遊戲歷史失敗: {e}")
            return []
    
    def get_available_games(self):
        """獲取可用的遊戲類型"""
        return [
            {
                'type': 'capital_cities',
                'name': '首都城市問答',
                'description': '測試你對世界首都的了解',
                'difficulty': '簡單'
            },
            {
                'type': 'simple_math', 
                'name': '簡單數學題',
                'description': '基礎算術練習',
                'difficulty': '簡單'
            },
            {
                'type': 'memory_sequence',
                'name': '數字序列記憶',
                'description': '觀察數字規律',
                'difficulty': '中等'
            },
            {
                'type': 'word_memory',
                'name': '詞語記憶遊戲',
                'description': '記憶相關詞語',
                'difficulty': '中等'
            }
        ]

# 全局遊戲系統實例
memory_games = MemoryGameSystem()