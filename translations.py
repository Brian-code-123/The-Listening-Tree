# -*- coding: utf-8 -*-
"""
Language translations for the Elderly Companion Chatbot
Supports: English (en), Traditional Chinese (zh-HK for Cantonese)
"""

TRANSLATIONS = {
    'en': {
        # Navigation & Layout
        'app_name': 'The Listening Tree',
        'tagline': 'Your friendly companion',
        'logout': 'Logout',
        'language': 'Language',
        'accessibility_mode': 'Accessibility Mode',
        'normal_mode': 'Normal Mode',
        'guidance': 'Guidance',
        
        # Chat Interface
        'type_message': 'Type your message...',
        'recording': 'Recording...',
        'send': 'Send',
        'start_voice': 'Start Voice',
        'stop_voice': 'Stop Voice',
        
        # Authentication
        'login': 'Login',
        'register': 'Register',
        'email': 'Email',
        'password': 'Password',
        'confirm_password': 'Confirm Password',
        'remember_me': 'Remember me',
        'already_have_account': 'Already have an account?',
        'no_account': "Don't have an account?",
        
        # Reminders
        'reminders': 'Reminders',
        'active_reminders': 'Active Reminders',
        'set_reminder': 'Set Reminder',
        'no_reminders': 'No active reminders',
        'reminder_format': 'Format: set reminder [activity] [HH:MM]',
        
        # Games & Activities
        'play_game': 'Play Game',
        'start_quiz': 'Start Quiz',
        'your_score': 'Your score',
        'correct': 'Correct!',
        'incorrect': 'Incorrect. Try again!',
        
        # Accessibility
        'high_contrast': 'High Contrast Mode',
        'large_text': 'Large Text',
        'voice_control': 'Voice Control',
        'accessibility_title': 'Accessibility Settings',
        'accessibility_desc': 'This page is optimized for users with visual impairment',
        
        # Guidance
        'welcome': 'Welcome',
        'how_to_use': 'How to Use',
        'example_questions': 'Example Questions',
        'commands': 'Available Commands',
        'need_help': 'Need Help?',
        
        # Example prompts
        'example_1': 'How are you today?',
        'example_2': 'Tell me a joke',
        'example_3': 'What can you help me with?',
        'example_4': 'Set reminder for medicine at 09:00',
        'example_5': 'Play a memory game',
        'example_6': 'What is the weather like?',
        
        # Commands help
        'cmd_reminder': 'Set reminder [activity] [time]',
        'cmd_delete': 'Delete reminder [activity]',
        'cmd_game': 'Play game',
        'cmd_answer': 'Answer [your answer]',
        
        # Error messages
        'error_generic': 'Something went wrong. Please try again.',
        'error_voice': 'Could not access microphone. Please check permissions.',
        'error_network': 'Network error. Please check your connection.',
    },
    
    'zh-HK': {
        # Navigation & Layout
        'app_name': '聆聽樹',
        'tagline': '您的友善夥伴',
        'logout': '登出',
        'language': '語言',
        'accessibility_mode': '無障礙模式',
        'normal_mode': '普通模式',
        'guidance': '使用指引',
        
        # Chat Interface
        'type_message': '輸入您的訊息...',
        'recording': '錄音中...',
        'send': '發送',
        'start_voice': '開始語音',
        'stop_voice': '停止語音',
        
        # Authentication
        'login': '登入',
        'register': '註冊',
        'email': '電郵',
        'password': '密碼',
        'confirm_password': '確認密碼',
        'remember_me': '記住我',
        'already_have_account': '已有帳戶？',
        'no_account': '還沒有帳戶？',
        
        # Reminders
        'reminders': '提醒',
        'active_reminders': '活躍提醒',
        'set_reminder': '設置提醒',
        'no_reminders': '沒有活躍的提醒',
        'reminder_format': '格式：設置提醒 [活動] [HH:MM]',
        
        # Games & Activities
        'play_game': '玩遊戲',
        'start_quiz': '開始問答',
        'your_score': '您的分數',
        'correct': '正確！',
        'incorrect': '不正確。請再試！',
        
        # Accessibility
        'high_contrast': '高對比度模式',
        'large_text': '大字體',
        'voice_control': '語音控制',
        'accessibility_title': '無障礙設定',
        'accessibility_desc': '此頁面為視力模糊的長者特別優化',
        
        # Guidance
        'welcome': '歡迎',
        'how_to_use': '如何使用',
        'example_questions': '示例問題',
        'commands': '可用指令',
        'need_help': '需要幫助？',
        
        # Example prompts
        'example_1': '你今日點呀？',
        'example_2': '講個笑話聽吓',
        'example_3': '你可以幫我啲咩？',
        'example_4': '設置提醒食藥09:00',
        'example_5': '玩記憶遊戲',
        'example_6': '天氣點樣？',
        
        # Commands help
        'cmd_reminder': '設置提醒 [活動] [時間]',
        'cmd_delete': '刪除提醒 [活動]',
        'cmd_game': '玩遊戲',
        'cmd_answer': '答案 [您的答案]',
        
        # Error messages
        'error_generic': '發生錯誤。請再試。',
        'error_voice': '無法使用麥克風。請檢查權限。',
        'error_network': '網絡錯誤。請檢查連接。',
    }
}

def get_text(key, lang='en'):
    """Get translated text for a given key and language"""
    return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)

def get_all_translations(lang='en'):
    """Get all translations for a specific language"""
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])
