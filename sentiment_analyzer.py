import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import numpy as np
from datetime import datetime
import json
import sqlite3
from typing import Dict, List, Tuple

class AdvancedSentimentAnalyzer:
    def __init__(self, model_name="cardiffnlp/twitter-roberta-base-sentiment-latest"):
        """
        高級情感分析器
        Args:
            model_name: 預訓練模型名稱
            - cardiffnlp/twitter-roberta-base-sentiment-latest (推薦，專門訓練於社交文本)
            - distilbert-base-uncased-finetuned-sst-2-english (輕量級)
            - nlptown/bert-base-multilingual-uncased-sentiment (多語言)
        """
        print("加載情感分析模型中...")
        
        # 加載模型和分詞器
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        
        # 情感分類器 pipeline
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model=self.model,
            tokenizer=self.tokenizer,
            return_all_scores=True
        )
        
        # 情感詞典（用於增強分析）
        self.emotion_lexicon = self._load_emotion_lexicon()
        
        # 初始化數據庫
        self.setup_database()
    
    def _load_emotion_lexicon(self) -> Dict[str, List[str]]:
        """加載情感詞典"""
        return {
            'positive': [
                '開心', '高興', '快樂', '滿意', '喜歡', '愛', '美好', '幸福', '舒服',
                '高興', '愉快', '興奮', '感激', '安心', '放鬆', '溫暖', '希望'
            ],
            'negative': [
                '難過', '傷心', '痛苦', '孤獨', '寂寞', '害怕', '擔心', '焦慮', '生氣',
                '憤怒', '失望', '沮喪', '疲憊', '不舒服', '疼痛', '無助', '絕望'
            ],
            'urgent': [
                '救命', '幫助', '緊急', '快點', '立即', '馬上', '不舒服', '疼痛',
                '摔倒', '頭暈', '呼吸困難', '胸痛'
            ]
        }
    
    def setup_database(self):
        """初始化情感分析數據庫"""
        self.conn = sqlite3.connect('elderly_chatbot.db', check_same_thread=False)
        self._create_sentiment_tables()
    
    def _create_sentiment_tables(self):
        """創建情感分析相關數據表"""
        # 情感歷史表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS sentiment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                message TEXT,
                sentiment_label TEXT,
                sentiment_score REAL,
                emotion_tags TEXT,
                urgency_level INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 情感趨勢表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS sentiment_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                date DATE,
                avg_sentiment REAL,
                positive_count INTEGER,
                negative_count INTEGER,
                urgent_count INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        self.conn.commit()
    
    def analyze_sentiment(self, text: str, user_id: str = "default") -> Dict:
        """
        分析文本情感
        Returns:
            {
                'label': 'POSITIVE/NEGATIVE/NEUTRAL',
                'score': 0.95,
                'emotions': ['happy', 'grateful'],
                'urgency_level': 0-3,
                'recommendation': '建議的回應策略'
            }
        """
        try:
            # 使用深度學習模型分析
            dl_result = self._deep_learning_analysis(text)
            
            # 使用規則基礎分析增強
            rule_result = self._rule_based_analysis(text)
            
            # 合併結果
            final_sentiment = self._merge_analysis_results(dl_result, rule_result)
            
            # 生成回應建議
            final_sentiment['recommendation'] = self._generate_recommendation(final_sentiment)
            
            # 保存分析結果
            self._save_sentiment_analysis(user_id, text, final_sentiment)
            
            return final_sentiment
            
        except Exception as e:
            print(f"情感分析錯誤: {e}")
            return self._get_fallback_sentiment()
    
    def _deep_learning_analysis(self, text: str) -> Dict:
        """使用深度學習模型分析情感"""
        try:
            # 使用 pipeline 進行情感分析
            results = self.sentiment_pipeline(text)
            
            # 處理結果
            if results and len(results) > 0:
                scores = results[0]  # 獲取第一個結果的所有分數
                
                # 找到最高分的情感標籤
                best_score = max(scores, key=lambda x: x['score'])
                
                return {
                    'label': best_score['label'].upper(),
                    'score': best_score['score'],
                    'all_scores': scores
                }
            
        except Exception as e:
            print(f"深度學習分析錯誤: {e}")
        
        return {'label': 'NEUTRAL', 'score': 0.5, 'all_scores': []}
    
    def _rule_based_analysis(self, text: str) -> Dict:
        """基於規則的情感分析"""
        emotions_detected = []
        urgency_level = 0
        
        text_lower = text.lower()
        
        # 檢測情感詞彙
        for emotion_type, words in self.emotion_lexicon.items():
            for word in words:
                if word in text_lower:
                    if emotion_type == 'positive':
                        emotions_detected.append('positive')
                    elif emotion_type == 'negative':
                        emotions_detected.append('negative')
                    elif emotion_type == 'urgent':
                        urgency_level = max(urgency_level, 2)  # 中等緊急
        
        # 檢測感嘆號和問號（緊急信號）
        if '!' in text or '？' in text or '?' in text:
            urgency_level = max(urgency_level, 1)
        
        # 檢測緊急詞彙組合
        urgent_combinations = [
            ['幫助', '現在'], ['救命', '快'], ['疼痛', '嚴重'], ['呼吸', '困難']
        ]
        
        for combo in urgent_combinations:
            if all(word in text_lower for word in combo):
                urgency_level = 3  # 高度緊急
        
        return {
            'emotions': list(set(emotions_detected)),
            'urgency_level': urgency_level
        }
    
    def _merge_analysis_results(self, dl_result: Dict, rule_result: Dict) -> Dict:
        """合併深度學習和規則基礎的分析結果"""
        final_result = {
            'label': dl_result.get('label', 'NEUTRAL'),
            'score': dl_result.get('score', 0.5),
            'emotions': rule_result.get('emotions', []),
            'urgency_level': rule_result.get('urgency_level', 0)
        }
        
        # 如果規則檢測到緊急情況，優先考慮
        if rule_result['urgency_level'] >= 2:
            final_result['label'] = 'URGENT'
            final_result['score'] = 0.9
        
        return final_result
    
    def _generate_recommendation(self, sentiment: Dict) -> str:
        """根據情感分析生成回應建議"""
        label = sentiment['label']
        urgency = sentiment['urgency_level']
        
        if urgency >= 3:
            return "立即提供幫助，建議聯繫緊急聯絡人"
        elif urgency >= 2:
            return "表達關心和安慰，詢問具體需求"
        
        if label == 'POSITIVE':
            if sentiment['score'] > 0.8:
                return "積極回應，分享喜悅，鼓勵繼續保持"
            else:
                return "溫和肯定，提供積極反饋"
        
        elif label == 'NEGATIVE':
            if sentiment['score'] > 0.7:
                return "表達同理心，提供情感支持，建議放鬆活動"
            else:
                return "溫和關心，詢問具體情況，提供幫助"
        
        else:  # NEUTRAL or URGENT
            return "常規回應，保持友好，鼓勵分享更多"
    
    def _save_sentiment_analysis(self, user_id: str, text: str, sentiment: Dict):
        """保存情感分析結果"""
        try:
            self.conn.execute('''
                INSERT INTO sentiment_history 
                (user_id, message, sentiment_label, sentiment_score, emotion_tags, urgency_level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                text,
                sentiment['label'],
                sentiment['score'],
                json.dumps(sentiment['emotions'], ensure_ascii=False),
                sentiment['urgency_level']
            ))
            self.conn.commit()
            
            # 更新情感趨勢
            self._update_sentiment_trends(user_id)
            
        except Exception as e:
            print(f"保存情感分析結果錯誤: {e}")
    
    def _update_sentiment_trends(self, user_id: str):
        """更新用戶情感趨勢"""
        try:
            today = datetime.now().date()
            
            # 計算今日情感統計
            cursor = self.conn.execute('''
                SELECT 
                    AVG(sentiment_score) as avg_score,
                    COUNT(CASE WHEN sentiment_label = 'POSITIVE' THEN 1 END) as positive_count,
                    COUNT(CASE WHEN sentiment_label = 'NEGATIVE' THEN 1 END) as negative_count,
                    COUNT(CASE WHEN urgency_level >= 2 THEN 1 END) as urgent_count
                FROM sentiment_history 
                WHERE user_id = ? AND DATE(timestamp) = ?
            ''', (user_id, today))
            
            result = cursor.fetchone()
            
            if result:
                self.conn.execute('''
                    INSERT OR REPLACE INTO sentiment_trends 
                    (user_id, date, avg_sentiment, positive_count, negative_count, urgent_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, today, *result))
                self.conn.commit()
                
        except Exception as e:
            print(f"更新情感趨勢錯誤: {e}")
    
    def get_sentiment_trends(self, user_id: str, days: int = 7) -> List[Dict]:
        """獲取用戶情感趨勢"""
        try:
            cursor = self.conn.execute('''
                SELECT date, avg_sentiment, positive_count, negative_count, urgent_count
                FROM sentiment_trends 
                WHERE user_id = ? AND date >= date('now', ?)
                ORDER BY date DESC
            ''', (user_id, f'-{days} days'))
            
            trends = []
            for row in cursor.fetchall():
                trends.append({
                    'date': row[0],
                    'avg_sentiment': row[1],
                    'positive_count': row[2],
                    'negative_count': row[3],
                    'urgent_count': row[4]
                })
            
            return trends
            
        except Exception as e:
            print(f"獲取情感趨勢錯誤: {e}")
            return []
    
    def _get_fallback_sentiment(self) -> Dict:
        """獲取備用情感分析結果"""
        return {
            'label': 'NEUTRAL',
            'score': 0.5,
            'emotions': [],
            'urgency_level': 0,
            'recommendation': '常規回應'
        }

# 全局情感分析器實例
sentiment_analyzer = AdvancedSentimentAnalyzer()