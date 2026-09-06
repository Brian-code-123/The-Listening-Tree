"""Core chat message handler (/get_response) — command routing, quiz-game
state machine, and the AI fallthrough — plus voice transcription and
device-token registration.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.background import prune_user_chat_history
from app.core import config
from app.core.session import get_lang, get_user
from app.db import queries as db
from app.routers.conversations import get_or_create_active_conversation
from app.services.ai import call_ai
from app.services.quiz import is_quiz_answer_correct, questions, questions_zh
from app.services.reminders import create_reminder, delete_reminder_by_label
from app.services import transcription as stt
from app.services.rate_limit import check_and_increment, client_key
from translations import get_text

logger = logging.getLogger(__name__)

router = APIRouter()

# Voice clips are naturally chunky (a few seconds of audio each) and the
# elderly-friendly UI encourages retries, so this is looser than the auth
# routes' limits — generous enough for real use, still bounds a script
# hammering the Whisper/SpeechRecognition backends.
TRANSCRIBE_RATE_LIMIT = 20
RATE_LIMIT_WINDOW_SECONDS = 60


# ---------------------------------------------------------------------------
# Command handlers
#
# Each returns the bot's reply text. None of them touch the connection's
# lifecycle — get_response owns opening, committing, and closing — except
# _handle_set_preference, which keeps its own pre-existing mid-flight
# commit.
# ---------------------------------------------------------------------------
def _guide_trigger_response(user_input_original: str, user_input_lower: str, lang: str) -> Optional[str]:
    """Reply text for the 'how do I use this' keywords, or None."""
    guide_triggers_zh = ['教', '點用', '唔明', '幫教']
    guide_triggers_en = ['teach', 'how to use', 'help me', 'guide']
    if lang == 'zh-HK':
        is_guide_trigger = any(t in user_input_original for t in guide_triggers_zh)
    else:
        is_guide_trigger = any(t in user_input_lower for t in guide_triggers_en)

    if not is_guide_trigger:
        return None

    if lang == 'zh-HK':
        return ("📖 你可以撳右下角嘅「？」按鈕打開操作指引！入面有所有功能嘅使用方法。\n\n"
                "簡單指令：\n"
                "• 打字或者講嘢同我傾偈\n"
                "• 「設置提醒 食藥 09:00」設提醒\n"
                "• 「玩遊戲」開始問答遊戲\n"
                "• 撳🔍按鈕搜尋網頁\n"
                "• 撳📎按鈕上傳檔案")
    return ("📖 Click the '?' button at the bottom-right to open the Operation Guide!\n\n"
            "Quick commands:\n"
            "• Type or speak to chat with me\n"
            "• 'set reminder take medicine 09:00' to set a reminder\n"
            "• 'play game' to start a quiz\n"
            "• Click 🔍 button for web search\n"
            "• Click 📎 button to upload files")


def _parse_reminder_set_command(user_input_original: str, user_input_lower: str):
    """Pull (label, time_str) out of a 'set reminder' command.

    Returns (label, time_str, None) on success, or (None, None, usage_text)
    when the command is malformed — the usage text follows the command's
    own language, not the UI language.
    """
    if user_input_lower.startswith("設置提醒"):
        parts = user_input_original.split()
        if len(parts) >= 3 and ':' in parts[-1]:
            return ' '.join(parts[1:-1]), parts[-1], None
        return None, None, "格式：設置提醒 [活動] [HH:MM]"

    parts = user_input_lower.split()
    if len(parts) >= 4 and len(parts[-1]) == 5 and parts[-1][2] == ':':
        return ' '.join(parts[2:-1]), parts[-1], None
    return None, None, "Usage: set reminder [activity] [HH:MM]"


async def _apply_reminder_set(uid: int, label: str, time_str: str, lang: str) -> str:
    """Create the reminder, or explain why the time was rejected."""
    try:
        h, m = map(int, time_str.split(':'))
        if 0 <= h <= 23 and 0 <= m <= 59:
            await create_reminder(uid, label, time_str)
            return f"提醒已設置：{label}，時間 {time_str}" if lang == 'zh-HK' else f"Reminder set: {label} at {time_str}"
        return "時間無效。請用24小時格式 HH:MM" if lang == 'zh-HK' else "Invalid time. Use 24-hour format HH:MM"
    except (ValueError, IndexError):
        # Malformed time strings (bad separators, non-numeric values).
        return "時間格式錯誤。請用 HH:MM" if lang == 'zh-HK' else "Invalid time format. Use HH:MM"


async def _handle_reminder_delete(uid: int, user_input_original: str, user_input_lower: str, lang: str) -> str:
    if user_input_lower.startswith("刪除提醒"):
        parts = user_input_original.split(maxsplit=1)
        label = parts[1] if len(parts) == 2 else None
    else:
        parts = user_input_lower.split(maxsplit=2)
        label = parts[2] if len(parts) == 3 else None

    if not label:
        return "格式：刪除提醒 [活動]" if lang == 'zh-HK' else "Usage: delete reminder [activity]"

    found = await delete_reminder_by_label(uid, label)
    if found:
        return f"已刪除提醒：{label}" if lang == 'zh-HK' else f"Deleted reminder: {label}"
    return "搵唔到呢個提醒。" if lang == 'zh-HK' else "No reminder found with that name."


async def _handle_set_preference(c, conn, uid: int, user_input_lower: str, timestamp: str) -> str:
    parts = user_input_lower.split(maxsplit=4)
    if len(parts) < 4:
        return "Usage: set preference [key] [value]"
    key, value = parts[2], parts[3]
    await db.db_insert_or_replace_preference(c, uid, key, value, timestamp)
    await conn.commit()
    return f"Preference updated: {key} = {value}"


ANSWER_PREFIXES = ["answer ", "答案 ", "答案：", "答案:", "回答 ", "答 "]
ANSWER_ONLY_TOKENS = {"answer", "答案", "回答", "答"}
GAME_TRIGGERS = ["play game", "玩遊戲", "玩游戏"]
EXIT_TRIGGERS = ["exit game", "退出遊戲", "退出游戏"]


def _load_game_state(request: Request, uid: int, lang: str) -> dict:
    """Session state wins over the in-process dict: it survives reloads and
    worker boundaries, which the process memory doesn't.
    """
    defaults = {
        'is_game_mode': False,
        'current_index': 0,
        'current_question': None,
        'correct_answer': None,
        'score': 0,
        'lang': lang,
    }
    stored = request.session.get('game_state')
    if isinstance(stored, dict):
        return {**defaults, **stored}
    return {**defaults, **config.user_game_states.get(uid, {})}


async def _restore_game_from_history(c, uid: int, game: dict, game_lang: str, active_questions) -> bool:
    """Re-enter game mode if the last bot message was a quiz question.

    Covers the case where the session lost its game state (reload, worker
    switch) mid-game. Returns whether anything was restored, so the caller
    knows to persist.
    """
    try:
        await db.db_execute(
            c,
            "SELECT message FROM chat_history WHERE user_id = ? AND lang = ? AND is_bot = TRUE ORDER BY timestamp DESC LIMIT 1",
            (uid, game_lang),
        )
        last_bot = c.fetchone()
        last_text = (last_bot[0] if isinstance(last_bot, (list, tuple)) else (last_bot.get('message') if last_bot else '')) if last_bot else ''
    except Exception:
        last_text = ''
    if not last_text:
        return False

    for idx, q in enumerate(active_questions):
        if q['question'] and q['question'] in last_text:
            game['is_game_mode'] = True
            game['current_index'] = idx
            game['current_question'] = q['question']
            game['correct_answer'] = q['answer']
            return True
    return False


def _strip_answer_prefix(user_input_original: str, user_input_lower: str) -> tuple[str, str]:
    """Drop a leading "answer"/"答案" style prefix, returning the bare answer
    and its lowercased form.
    """
    answer_text = user_input_original.strip()
    answer_text_lower = user_input_lower.strip()
    for prefix in ANSWER_PREFIXES:
        if answer_text_lower.startswith(prefix):
            answer_text = answer_text[len(prefix):].strip()
            answer_text_lower = answer_text.lower()
            break
    return answer_text, answer_text_lower


def _start_game(game: dict, active_questions, lang: str) -> str:
    game['is_game_mode'] = True
    game['current_index'] = 0
    game['score'] = 0
    game['lang'] = lang
    q = active_questions[0]
    game['current_question'] = q["question"]
    game['correct_answer'] = q["answer"]
    if lang == 'zh-HK':
        return f"開始玩喇！一共有{len(active_questions)}條問題。分數：0。第一條問題：{game['current_question']}"
    return f"Let's play! You have {len(active_questions)} questions. Current score: 0. First question: {game['current_question']}"


def _stop_game(game: dict, lang: str) -> str:
    game['is_game_mode'] = False
    if lang == 'zh-HK':
        return f"遊戲結束！你答啱咗{game['score']}條（總共{game['current_index']}條）。"
    return f"Game stopped. You got {game['score']} out of {game['current_index']} correct so far!"


def _grade_answer(game: dict, answer_text: str, lang: str) -> str:
    """Score the answer against the current question."""
    if is_quiz_answer_correct(answer_text, game['correct_answer']):
        game['score'] += 1
        return f"啱咗！分數：{game['score']}" if lang == 'zh-HK' else f"Correct! Score: {game['score']}"
    if lang == 'zh-HK':
        return f"唔啱呀，答案係{game['correct_answer']}。分數：{game['score']}"
    return f"Incorrect. The answer was {game['correct_answer']}. Score: {game['score']}"


def _advance_question(game: dict, active_questions, lang: str) -> str:
    """Move to the next question, or end the game if that was the last one.
    Returns the text to append to the answer's own feedback.
    """
    game['current_index'] += 1
    if game['current_index'] == len(active_questions):
        game['is_game_mode'] = False
        if lang == 'zh-HK':
            return f"\n遊戲完成！你答啱咗{game['score']}條（總共{len(active_questions)}條）。叻叻！"
        return f"\nGame over! You successfully answered {game['score']} out of {len(active_questions)} questions correctly."

    q = active_questions[game['current_index']]
    game['current_question'] = q["question"]
    game['correct_answer'] = q["answer"]
    if lang == 'zh-HK':
        return f" 下一條問題：{q['question']}"
    return f" Next question: {q['question']}"


async def _handle_quiz_game(request: Request, c, uid: int, lang: str, user_input_original: str, user_input_lower: str) -> Optional[str]:
    """Run the quiz state machine, or return None if this message isn't
    game-related and should fall through to the AI.

    The pieces that only touch one part of the state (loading, restoring,
    starting, stopping, parsing an answer) are their own functions above.
    What stays here is the part that genuinely can't be pulled apart:
    grading an answer and advancing the game read and write the same
    `score` / `current_index` / `current_question` / `correct_answer` /
    `is_game_mode` fields in sequence, and each step's result decides what
    the next one does — grading feeds the score into the advance, and the
    advance decides whether the game is still running for the next message.
    """
    game = _load_game_state(request, uid, lang)
    game_lang = game.get('lang', lang)
    # Treat any zh-* language code as Chinese so users with 'zh',
    # 'zh-CN', or 'zh-HK' preferences get the Chinese question set.
    active_questions = questions_zh if (isinstance(game_lang, str) and game_lang.startswith('zh')) else questions

    def persist() -> None:
        request.session['game_state'] = game
        config.user_game_states[uid] = game

    if not game['is_game_mode'] and await _restore_game_from_history(c, uid, game, game_lang, active_questions):
        persist()

    if user_input_lower in GAME_TRIGGERS and not game['is_game_mode']:
        response = _start_game(game, active_questions, lang)
        persist()
        return response

    if user_input_lower in EXIT_TRIGGERS and game['is_game_mode']:
        response = _stop_game(game, lang)
        persist()
        return response

    if game['is_game_mode']:
        answer_text, answer_text_lower = _strip_answer_prefix(user_input_original, user_input_lower)
        if answer_text_lower in ANSWER_ONLY_TOKENS or not answer_text:
            if lang == 'zh-HK':
                response = f"請輸入答案內容先喔。呢條問題係：{game['current_question']}"
            else:
                response = f"Please type your answer after 'answer'. Current question: {game['current_question']}"
            persist()
            return response

        response = _grade_answer(game, answer_text, lang)
        response += _advance_question(game, active_questions, lang)
        persist()
        return response

    if user_input_lower.startswith("answer") or user_input_lower.startswith("答案") or user_input_lower.startswith("回答"):
        return (
            "你未開始遊戲呀，請先輸入「玩遊戲」。" if lang == 'zh-HK'
            else "You're not in a game yet. Type 'play game' first."
        )

    return None


async def _handle_ai_fallback(c, uid: int, lang: str, user_input_original: str, conversation_id: int) -> str:
    await db.db_execute(c, "SELECT username FROM users WHERE id = ?", (uid,))
    user_row = c.fetchone()
    display_name = user_row["username"] if user_row else None
    return await call_ai(c, user_input_original, uid, lang, display_name=display_name, conversation_id=conversation_id)


# ---------------------------------------------------------------------------
# Chat Response — the core message handler
#
# Accepts free-text input from the user, checks for special command
# prefixes (reminders, games, preferences), and falls through to the
# Zhipu AI LLM for general conversation.
# ---------------------------------------------------------------------------
@router.post("/get_response")
async def get_response(request: Request, msg: str = Form(...), conversation_id: Optional[int] = Form(None)):
    """Process user message and return AI/command response."""
    uid = get_user(request)
    if uid is None:
        return JSONResponse({"response": "Please log in."}, status_code=401)

    lang = get_lang(request)
    user_input_original = msg.strip()
    user_input_lower = user_input_original.lower()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = await db.get_db()
    c = conn.cursor()

    # conversation_id is optional so older/other callers (voice shortcuts,
    # the reminder-delete quick action) keep working unchanged — they just
    # land in the user's most recent conversation instead of a specific one.
    conversation_id = await get_or_create_active_conversation(c, uid, lang, conversation_id)

    # Store user message
    await db.db_execute(
        c,
        "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, FALSE, ?, FALSE, ?)",
        (uid, lang, timestamp, user_input_original, conversation_id),
    )
    # Auto-title from the first message in this conversation; COALESCE makes
    # this a no-op once a title already exists.
    preview_title = user_input_original.replace("\n", " ").replace("\r", " ").strip()[:40]
    await db.db_execute(
        c,
        "UPDATE conversations SET title = COALESCE(title, ?), updated_at = ? WHERE id = ?",
        (preview_title or None, timestamp, conversation_id),
    )
    await conn.commit()

    guide_response = _guide_trigger_response(user_input_original, user_input_lower, lang)

    if guide_response is not None:
        response = guide_response

    elif user_input_lower.startswith("set reminder") or user_input_lower.startswith("設置提醒"):
        label, time_str, usage_error = _parse_reminder_set_command(user_input_original, user_input_lower)
        if usage_error is not None:
            await db.db_execute(c, "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, TRUE, ?, FALSE, ?)", (uid, lang, timestamp, usage_error, conversation_id))
            await conn.commit(); await conn.close()
            return JSONResponse({"response": usage_error})
        response = await _apply_reminder_set(uid, label, time_str, lang)

    elif user_input_lower.startswith("delete reminder") or user_input_lower.startswith("刪除提醒"):
        response = await _handle_reminder_delete(uid, user_input_original, user_input_lower, lang)

    elif user_input_lower.startswith("set preference"):
        response = await _handle_set_preference(c, conn, uid, user_input_lower, timestamp)

    else:
        game_response = await _handle_quiz_game(request, c, uid, lang, user_input_original, user_input_lower)
        if game_response is not None:
            response = game_response
        else:
            response = await _handle_ai_fallback(c, uid, lang, user_input_original, conversation_id)

    # Store bot response
    await db.db_execute(
        c,
        "INSERT INTO chat_history (user_id, lang, timestamp, is_bot, message, is_deleted, conversation_id) VALUES (?, ?, ?, TRUE, ?, FALSE, ?)",
        (uid, lang, timestamp, response, conversation_id),
    )

    # Keep recent history stable across Vercel/local/mobile by pruning oldest rows.
    await prune_user_chat_history(c, conversation_id)
    await conn.commit()
    await conn.close()

    return JSONResponse({"response": response})


# ---------------------------------------------------------------------------
# Voice Transcription
# ---------------------------------------------------------------------------
STT_LANGUAGE_ALIASES = {
    "en": "en-US",
    "en-us": "en-US",
    "zh": "zh-HK",
    "zh-hk": "zh-HK",
    "zh_HK": "zh-HK",
}


def _reject_upload_before_reading(request: Request, audio: UploadFile) -> Optional[JSONResponse]:
    """Checks that can run off the headers alone, so an oversized or
    non-audio upload is turned away without reading the body first.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > stt.MAX_TRANSCRIBE_UPLOAD_BYTES:
        return JSONResponse({"text": "", "error": "Audio file too large."}, status_code=413)
    if audio.content_type and not audio.content_type.startswith("audio/"):
        return JSONResponse({"text": "", "error": "Expected an audio file."}, status_code=415)
    return None


def _reject_audio_payload(content: bytes) -> Optional[JSONResponse]:
    """Checks that need the bytes. Takes the already-read payload rather than
    the UploadFile: its stream can only be consumed once, and a second read()
    returns empty bytes instead of raising.
    """
    if not content:
        return JSONResponse({"text": "", "error": "Empty audio payload."}, status_code=400)
    if len(content) > stt.MAX_TRANSCRIBE_UPLOAD_BYTES:
        return JSONResponse({"text": "", "error": "Audio file too large."}, status_code=413)
    return None


async def _run_stt(content: bytes, language: str, lang: str) -> JSONResponse:
    """Whisper first, Google Web Speech as the fallback. `language` is the
    speech locale for Google; `lang` is the UI language for error messages.
    """
    if stt.HF_API_KEY:
        try:
            text = await stt.transcribe_with_hf_whisper(content)
            if text:
                return JSONResponse({"text": text, "engine": stt.HF_WHISPER_MODEL})
            return JSONResponse(
                {"text": "", "error": get_text("no_speech_detected", lang)},
                status_code=422,
            )
        except Exception as e:
            logger.warning(f"[STT] Whisper (HF) error, falling back: {e}")

    if stt.sr is None:
        return JSONResponse(
            {"text": "", "error": "Server STT dependency missing (SpeechRecognition)."},
            status_code=503,
        )

    try:
        text = stt.transcribe_with_google_fallback(content, language)
        return JSONResponse({"text": text, "engine": "google-web-speech"})
    except stt.sr.UnknownValueError:
        return JSONResponse(
            {"text": "", "error": get_text("no_speech_detected", lang)},
            status_code=422,
        )
    except stt.sr.RequestError as e:
        logger.error(f"[STT] upstream request error: {e}")
        return JSONResponse(
            {"text": "", "error": get_text("error_network", lang)},
            status_code=503,
        )
    except Exception as e:
        logger.error(f"[STT] transcribe error: {e}")
        return JSONResponse(
            {"text": "", "error": get_text("error_voice", lang)},
            status_code=500,
        )


@router.post("/transcribe")
async def transcribe_audio(request: Request, audio: UploadFile = File(...), lang: str = Form("en-US")):
    """Server-side STT. Primary engine: Whisper large-v3 (Hugging Face Inference
    API). Falls back to Google Web Speech (via SpeechRecognition) if no HF key
    is configured or the HF call fails.
    """
    if get_user(request) is None:
        return JSONResponse({"text": "", "error": "Not authenticated"}, status_code=401)

    if not await check_and_increment(client_key(request, "transcribe"), TRANSCRIBE_RATE_LIMIT, RATE_LIMIT_WINDOW_SECONDS):
        return JSONResponse({"text": "", "error": "Too many requests. Please wait a moment."}, status_code=429)

    rejected = _reject_upload_before_reading(request, audio)
    if rejected is not None:
        return rejected

    ui_lang = get_lang(request)
    language = (lang or ui_lang or "en").strip()
    language = STT_LANGUAGE_ALIASES.get(language.lower(), language)

    content = await audio.read()
    rejected = _reject_audio_payload(content)
    if rejected is not None:
        return rejected

    return await _run_stt(content, language, ui_lang)


@router.post("/register_device")
async def register_device(request: Request):
    try:
        data = await request.json()
        token = data.get("device_token")
        uid = get_user(request)
        if uid and token:
            # In a real setup, save this `token` to the database for this user
            logger.info(f"[Push] Registered device token for {uid}: {token}")
            return JSONResponse({"status": "ok"})
    except Exception:
        pass
    return JSONResponse({"status": "ignored"})
