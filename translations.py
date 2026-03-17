# -*- coding: utf-8 -*-
"""
translations.py — Internationalisation (i18n) strings for The Listening Tree.

Supported locales:
    en    — English (default)
    zh-HK — Traditional Chinese / Cantonese

Usage:
    from translations import get_text, get_all_translations
    label = get_text('app_name', 'zh-HK')   # → '聆聽樹'
    all_  = get_all_translations('en')       # full dict for templates
"""

# ---------------------------------------------------------------------------
# Master translation dictionary
#
# Each top-level key is a locale code.  Keys inside every locale dict
# correspond to UI labels, error messages, accessibility strings, etc.
# When a key is missing for a requested locale the English fallback is
# returned automatically by get_text().
# ---------------------------------------------------------------------------

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Navigation & Layout
        "app_name": "The Listening Tree",
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

        # Guidance / Guide Helper
        'welcome': 'Welcome',
        'how_to_use': 'How to Use',
        'example_questions': 'Example Questions',
        'commands': 'Available Commands',
        'need_help': 'Need Help?',
        'guide_helper': 'Guide Helper',
        'guide_title': 'Operation Guide',
        'guide_close': 'Close',
        'guide_chat_title': 'Chat',
        'guide_chat_desc': 'Type a message or press the microphone button to talk. Your companion will reply warmly.',
        'guide_voice_title': 'Voice Input',
        'guide_voice_desc': 'Press the mic button, speak clearly, and your words will be converted to text automatically.',
        'guide_reminder_title': 'Set Reminders',
        'guide_reminder_desc': 'Type "set reminder take medicine 09:00" or use the reminder panel on the right.',
        'guide_game_title': 'Play Games',
        'guide_game_desc': 'Type "play game" to start a fun quiz. Answer each question to earn points!',
        'guide_search_title': 'Web Search',
        'guide_search_desc': 'Click the search button to search the internet for answers.',
        'guide_upload_title': 'Upload Files',
        'guide_upload_desc': 'Click the upload button to share images or documents with us.',
        'guide_theme_title': 'Switch Theme',
        'guide_theme_desc': 'Click the sun/moon icon to switch between light and dark mode.',
        'guide_lang_title': 'Change Language',
        'guide_lang_desc': 'Click EN or 繁中 to switch language. Your chat history is saved per language.',

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

        # Auth - Login
        'welcome_back': 'Welcome Back!',
        'welcome_back_desc': "We're happy to see you again. Sign in to continue your journey with us.",
        'friendly_conversations': 'Friendly conversations',
        'voice_support': 'Voice support',
        'personalized_care': 'Personalized care',
        'sign_in': 'Sign In',
        'sign_in_desc': 'Please enter your details to continue',
        'forgot_password': 'Forgot password?',
        'need_help_title': 'Need Help?',
        'need_help_desc': 'If you have trouble logging in, please contact our support team. We are here to help you.',
        'show_password': 'Show password',

        # Auth - Register
        'join_community': 'Join Our Community!',
        'join_community_desc': 'Create your account and start your journey with us. It only takes a moment!',
        'safe_secure': 'Safe and secure',
        'supportive_community': 'Supportive community',
        'easy_to_use': 'Easy to use',
        'register_title': 'Register',
        'register_desc': 'Please fill in your details to get started',
        'password_hint': 'Use at least 8 characters with letters and numbers',
        'privacy_title': 'Your Privacy Matters',
        'privacy_desc': 'We protect your personal information and will never share it without your permission.',
        'passwords_match': 'Passwords match!',
        'passwords_no_match': 'Passwords do not match',

        # Accessibility page
        'skip_to_content': 'Skip to main content',
        'main_navigation': 'Main navigation',
        'language_selector': 'Language selector',
        'conversation': 'Conversation',
        'clear_chat': 'Clear all messages',
        'clear': 'Clear',
        'chat_messages': 'Chat messages',
        'assistant': 'Assistant',
        'welcome_message': 'Hello! How can I help you today? You can type your message or use voice input.',
        'just_now': 'Just now',
        'type_here': 'Type your message here...',
        'message_input': 'Message input field',
        'send_message': 'Send message',
        'start_recording': 'Start voice recording',
        'record': 'Record',
        'stop_recording': 'Stop voice recording',
        'stop': 'Stop',
        'toggle_speech': 'Toggle text-to-speech',
        'speak': 'Speak',
        'listen_msg': 'Listen',
        'voice_on': '🔊 Voice: ON',
        'voice_off': '🔇 Voice: OFF',
        'welcome_chat': 'Hello! I am your friendly companion. How are you today? 😊',
        'no_speech_support': 'Your browser does not support speech recognition. Please use Chrome or Edge.',
        'no_speech_detected': 'No speech detected. Please try again.',
        'mic_denied': 'Microphone access denied. Please check browser settings.',
        'processing': 'Processing audio...',
        'chat_cleared': 'Chat cleared',
        'tts_on': 'Text-to-speech enabled',
        'tts_off': 'Text-to-speech disabled',
        'page_loaded': 'Page loaded. Ready to chat.',
        'you': 'You',

        # New features: web search, file upload, theme
        'web_search': 'Web Search',
        'image_search': 'Image Search',
        'file_upload': 'Upload File',
        'upload_image': 'Upload Image',
        'dark_mode': 'Dark Mode',
        'light_mode': 'Light Mode',
        'theme_toggle': 'Toggle Theme',
        'searching': 'Searching the web...',
        'uploading': 'Uploading file...',
        'file_too_large': 'File is too large. Max 10MB.',
        'unsupported_file': 'Unsupported file type.',
        'search_enabled': 'Web search enabled for this message',
        'search_disabled': 'Web search disabled',

        # Calendar & Sidebar
        'calendar': 'Calendar',
        'today': 'Today',
        'public_holiday': 'Public Holiday',
        'no_holidays_today': 'No holidays today',
        'holidays_this_month': 'Holidays This Month',

        # News Section
        'news': 'Local News',
        'hk_news': 'Hong Kong News',
        'loading_news': 'Loading news...',
        'no_news': 'No news available right now.',
        'read_more': 'Read more',
        'news_summary': 'Summary',
        'refresh_news': 'Refresh',
        'news_source': 'Source',

        # Sidebar labels
        'sidebar_calendar': 'Calendar',
        'sidebar_reminders': 'Reminders',
        'sidebar_news': 'News',
        'todays_reminders': "Today's Reminders",
        'upcoming': 'Upcoming',
        'add_reminder': 'Add Reminder',
        'reminder_label': 'What to remind',
        'reminder_time_label': 'Time',
        'voice_read': 'Read aloud',

        # HK Local Guide
        'hk_guide_title': 'Hong Kong Local Guide',
        'hk_guide_back': 'Back to Chat',
        'hk_guide_all': 'All',
        'hk_guide_food': 'Food',
        'hk_guide_shopping': 'Shopping',
        'hk_guide_fun': 'Fun & Sights',
        'hk_guide_events': 'Events',
        'hk_guide_loading': 'Loading latest info...',
        'hk_guide_empty': 'No items found for this category.',
        'hk_guide_nav': 'HK Guide',
    },

    'zh-HK': {
        # Navigation & Layout
        'app_name': '聆聽樹',
        'tagline': '你嘅友善夥伴',
        'logout': '登出',
        'language': '語言',
        'accessibility_mode': '無障礙模式',
        'normal_mode': '普通模式',
        'guidance': '使用指引',

        # Chat Interface
        'type_message': '輸入你嘅訊息...',
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
        'no_account': '仲未有帳戶？',

        # Reminders
        'reminders': '提醒',
        'active_reminders': '活躍提醒',
        'set_reminder': '設置提醒',
        'no_reminders': '冇活躍嘅提醒',
        'reminder_format': '格式：設置提醒 [活動] [HH:MM]',

        # Games & Activities
        'play_game': '玩遊戲',
        'start_quiz': '開始問答',
        'your_score': '你嘅分數',
        'correct': '啱咗！',
        'incorrect': '唔啱呀。再試吓！',

        # Accessibility
        'high_contrast': '高對比度模式',
        'large_text': '大字體',
        'voice_control': '語音控制',
        'accessibility_title': '無障礙設定',
        'accessibility_desc': '呢頁為視力唔太好嘅長者特別優化',

        # Guidance / Guide Helper
        'welcome': '歡迎',
        'how_to_use': '點樣用',
        'example_questions': '示例問題',
        'commands': '可用指令',
        'need_help': '需要幫手？',
        'guide_helper': '指引助手',
        'guide_title': '操作指引',
        'guide_close': '關閉',
        'guide_chat_title': '傾偈',
        'guide_chat_desc': '打字或者撳咪高峰按鈕講嘢，我哋會溫暖咁回覆你。',
        'guide_voice_title': '語音輸入',
        'guide_voice_desc': '撳咪高峰按鈕，清楚咁講，你講嘅嘢會自動變成文字。',
        'guide_reminder_title': '設置提醒',
        'guide_reminder_desc': '打「設置提醒 食藥 09:00」或者用右邊嘅提醒面板。',
        'guide_game_title': '玩遊戲',
        'guide_game_desc': '打「玩遊戲」開始有趣嘅問答。答啱每條問題就得分！',
        'guide_search_title': '網頁搜尋',
        'guide_search_desc': '撳搜尋按鈕，等我哋幫你喺網上搵答案。',
        'guide_upload_title': '上傳檔案',
        'guide_upload_desc': '撳上傳按鈕，分享圖片或者文件畀我哋睇。',
        'guide_theme_title': '切換主題',
        'guide_theme_desc': '撳太陽/月亮圖示切換光亮同深暗模式。',
        'guide_lang_title': '轉換語言',
        'guide_lang_desc': '撳 EN 或 繁中 切換語言。每個語言嘅對話記錄會分開保存。',

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
        'cmd_answer': '答案 [你嘅答案]',

        # Error messages
        'error_generic': '出咗啲問題。請再試吓。',
        'error_voice': '用唔到咪高峰。請檢查權限。',
        'error_network': '網絡錯誤。請檢查連接。',

        # Auth - Login
        'welcome_back': '歡迎返嚟！',
        'welcome_back_desc': '好開心再見到你。登入繼續你嘅旅程啦。',
        'friendly_conversations': '友善對話',
        'voice_support': '語音支援',
        'personalized_care': '個人化關懷',
        'sign_in': '登入',
        'sign_in_desc': '請輸入你嘅資料繼續',
        'forgot_password': '忘記密碼？',
        'need_help_title': '需要幫手？',
        'need_help_desc': '如果登入有問題，請聯絡我哋嘅支援團隊。我哋隨時幫到你。',
        'show_password': '顯示密碼',

        # Auth - Register
        'join_community': '加入我哋！',
        'join_community_desc': '建立帳戶開始你嘅旅程，只需一陣！',
        'safe_secure': '安全可靠',
        'supportive_community': '互助社群',
        'easy_to_use': '容易使用',
        'register_title': '註冊',
        'register_desc': '請填寫你嘅資料開始',
        'password_hint': '至少用8個字符，包含字母同數字',
        'privacy_title': '你嘅隱私好重要',
        'privacy_desc': '我哋保護你嘅個人資料，絕對唔會未經許可分享。',
        'passwords_match': '密碼一致！',
        'passwords_no_match': '密碼唔一致',

        # Accessibility page
        'skip_to_content': '跳至主要內容',
        'main_navigation': '主要導航',
        'language_selector': '語言選擇',
        'conversation': '對話',
        'clear_chat': '清除所有訊息',
        'clear': '清除',
        'chat_messages': '對話訊息',
        'assistant': '助手',
        'welcome_message': '你好！我有咩可以幫到你？你可以打字或者用語音輸入。',
        'just_now': '剛剛',
        'type_here': '喺度輸入你嘅訊息...',
        'message_input': '訊息輸入欄',
        'send_message': '發送訊息',
        'start_recording': '開始錄音',
        'record': '錄音',
        'stop_recording': '停止錄音',
        'stop': '停止',
        'toggle_speech': '切換語音朗讀',
        'speak': '朗讀',
        'listen_msg': '聽回覆',
        'voice_on': '🔊 語音：開',
        'voice_off': '🔇 語音：關',
        'welcome_chat': '你好！我係你嘅友善夥伴。你今日過得點呀？😊',
        'no_speech_support': '你嘅瀏覽器唔支援語音辨識，請用 Chrome 或 Edge。',
        'no_speech_detected': '聽唔到語音，請再試一次。',
        'mic_denied': '咪高峰權限被拒絕，請檢查瀏覽器設定。',
        'processing': '處理緊音訊...',
        'chat_cleared': '對話已清除',
        'tts_on': '語音朗讀已開啟',
        'tts_off': '語音朗讀已關閉',
        'page_loaded': '頁面已載入。準備好傾偈啦。',
        'you': '你',

        # New features: web search, file upload, theme
        'web_search': '網頁搜尋',
        'image_search': '圖片搜尋',
        'file_upload': '上傳檔案',
        'upload_image': '上傳圖片',
        'dark_mode': '深暗模式',
        'light_mode': '光亮模式',
        'theme_toggle': '切換主題',
        'searching': '搜尋緊網頁...',
        'uploading': '上傳緊檔案...',
        'file_too_large': '檔案太大。最多10MB。',
        'unsupported_file': '唔支援呢種檔案類型。',
        'search_enabled': '呢條訊息已啟用網頁搜尋',
        'search_disabled': '網頁搜尋已關閉',

        # Calendar & Sidebar
        'calendar': '日曆',
        'today': '今日',
        'public_holiday': '公眾假期',
        'no_holidays_today': '今日冇假期',
        'holidays_this_month': '本月假期',

        # News Section
        'news': '本地新聞',
        'hk_news': '香港新聞',
        'loading_news': '載入新聞中...',
        'no_news': '暫時冇新聞。',
        'read_more': '閱讀更多',
        'news_summary': '摘要',
        'refresh_news': '刷新',
        'news_source': '來源',

        # Sidebar labels
        'sidebar_calendar': '日曆',
        'sidebar_reminders': '提醒',
        'sidebar_news': '新聞',
        'todays_reminders': '今日提醒',
        'upcoming': '即將到來',
        'add_reminder': '新增提醒',
        'reminder_label': '提醒內容',
        'reminder_time_label': '時間',
        'voice_read': '語音朗讀',

        # HK Local Guide
        'hk_guide_title': '香港本地攻略',
        'hk_guide_back': '返回傾偈',
        'hk_guide_all': '全部',
        'hk_guide_food': '美食',
        'hk_guide_shopping': '購物',
        'hk_guide_fun': '玩樂景點',
        'hk_guide_events': '活動',
        'hk_guide_loading': '載入最新資訊...',
        'hk_guide_empty': '呢個分類暫時冇項目。',
        'hk_guide_nav': '香港攻略',
    },
}


def get_text(key: str, lang: str = "en") -> str:
    """Return the translated string for *key* in the given *lang*.

    Falls back to English when the key is missing for the requested
    locale. If the key is absent in both locales the raw key string
    is returned as-is.
    """
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


def get_all_translations(lang: str = "en") -> dict[str, str]:
    """Return the entire translation dict for *lang* (or English)."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])
