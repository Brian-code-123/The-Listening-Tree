"""Bilingual memory-game (quiz) questions and answer-matching logic."""

# ---------------------------------------------------------------------------
# Quiz / Memory-game questions  (cognitive engagement feature)
#
# Answers are compared case-insensitively.  Keep answers as lowercase
# strings so the comparison in the game loop stays simple.
# ---------------------------------------------------------------------------

# Cantonese quiz questions
questions_zh = [
    {"question": "法國嘅首都係邊度？", "answer": "巴黎"},
    {"question": "2 + 2 等於幾多？", "answer": "4"},
    {"question": "晴天嘅天空係咩顏色？", "answer": "藍色"},
    {"question": "有一種水果，外面紅色，入面白色，有好多黑色嘅籽。係咩嚟㗎？", "answer": "西瓜"},
    {"question": "邊個月份有28日？", "answer": "每個月都有至少28日"},
    {"question": "水嘅化學符號係咩？", "answer": "h2o"},
]

# English quiz questions
questions = [
    {"question": "What's the capital of France?", "answer": "paris"},
    {"question": "What's 2 + 2?", "answer": "4"},
    {"question": "What color is the sky on a clear day?", "answer": "blue"},
    {"question": "There is a fruit with a red outer skin and white inside with small black seeds. What is it?", "answer": "watermelon"},
    {"question": "Which month has 28 days?", "answer": "every month has at least 28 days"},
    {"question": "What is the chemical symbol for water?", "answer": "h2o"}
]


def _normalize_quiz_answer(text: str) -> str:
    """Normalize quiz answers for tolerant matching.

    Strips spaces/punctuation and keeps letters/numbers/CJK characters only,
    so minor formatting differences do not break answer checking.
    """
    raw = str(text or "").strip().lower()
    return "".join(ch for ch in raw if ch.isalnum() or ('一' <= ch <= '鿿'))


def is_quiz_answer_correct(user_answer: str, correct_answer: str) -> bool:
    """Check if user answer is correct with intelligent substring matching.

    Accepts:
    1. Exact match (case-insensitive, ignoring spaces/punctuation)
    2. Substring match: user answer is a meaningful subset of correct answer
       (e.g., "每個月" matches "每個月都有至少28日")

    Only accept substring matches if user answer is at least 2 characters
    to avoid false positives.
    """
    norm_user = _normalize_quiz_answer(user_answer)
    norm_correct = _normalize_quiz_answer(correct_answer)

    # Exact match
    if norm_user == norm_correct:
        return True

    # Substring match: user answer is contained in correct answer
    if len(norm_user) >= 2 and norm_user in norm_correct:
        return True

    return False
