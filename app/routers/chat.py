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


async def _handle_quiz_game(request: Request, c, uid: int, lang: str, user_input_original: str, user_input_lower: str) -> Optional[str]:
    """Run the quiz state machine, or return None if this message isn't
    game-related and should fall through to the AI.

    Kept as one function on purpose: every branch mutates the same `game`
    dict and re-persists it through the same closure, so splitting it
    further would mean threading that state through more boundaries for
    no real gain.
    """
    game_defaults = {
        'is_game_mode': False,
        'current_index': 0,
        'current_question': None,
        'correct_answer': None,
        'score': 0,
        'lang': lang,
    }

    # Session-backed game state is more reliable than process memory and
    # avoids accidental mode loss across reloads or worker boundaries.
    stored_game = request.session.get('game_state')
    if isinstance(stored_game, dict):
        game = {**game_defaults, **stored_game}
    else:
        game = {**game_defaults, **config.user_game_states.get(uid, {})}

    game_lang = game.get('lang', lang)
    # Treat any zh-* language code as Chinese so users with 'zh',
    # 'zh-CN', or 'zh-HK' preferences get the Chinese question set.
    active_questions = questions_zh if (isinstance(game_lang, str) and game_lang.startswith('zh')) else questions

    def _persist_game_state() -> None:
        request.session['game_state'] = game
        config.user_game_states[uid] = game

    game_trigger = user_input_lower in ["play game", "玩遊戲", "玩游戏"]
    exit_trigger = user_input_lower in ["exit game", "退出遊戲", "退出游戏"]
    answer_prefixes = ["answer ", "答案 ", "答案：", "答案:", "回答 ", "答 "]
    answer_only_tokens = {"answer", "答案", "回答", "答"}

    # If the session lost game state but the last bot message was a quiz
    # question (e.g., page reload or worker switch), detect it from the
    # most recent bot message in chat_history and restore game mode.
    if not game.get('is_game_mode'):
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
        if last_text:
            for idx, q in enumerate(active_questions):
                if q['question'] and q['question'] in last_text:
                    game['is_game_mode'] = True
                    game['current_index'] = idx
                    game['current_question'] = q['question']
                    game['correct_answer'] = q['answer']
                    _persist_game_state()
                    break

    if game_trigger and not game['is_game_mode']:
        game['is_game_mode'] = True
        game['current_index'] = 0
        game['score'] = 0
        game['lang'] = lang
        q = active_questions[0]
        game['current_question'] = q["question"]
        game['correct_answer'] = q["answer"]
        if lang == 'zh-HK':
            response = f"開始玩喇！一共有{len(active_questions)}條問題。分數：0。第一條問題：{game['current_question']}"
        else:
            response = f"Let's play! You have {len(active_questions)} questions. Current score: 0. First question: {game['current_question']}"
        _persist_game_state()
        return response

    if exit_trigger and game['is_game_mode']:
        game['is_game_mode'] = False
        if lang == 'zh-HK':
            response = f"遊戲結束！你答啱咗{game['score']}條（總共{game['current_index']}條）。"
        else:
            response = f"Game stopped. You got {game['score']} out of {game['current_index']} correct so far!"
        _persist_game_state()
        return response

    if game['is_game_mode']:
        answer_text = user_input_original.strip()
        answer_text_lower = user_input_lower.strip()
        for prefix in answer_prefixes:
            if answer_text_lower.startswith(prefix):
                answer_text = answer_text[len(prefix):].strip()
                answer_text_lower = answer_text.lower()
                break

        if answer_text_lower in answer_only_tokens or not answer_text:
            if lang == 'zh-HK':
                response = f"請輸入答案內容先喔。呢條問題係：{game['current_question']}"
            else:
                response = f"Please type your answer after 'answer'. Current question: {game['current_question']}"
            _persist_game_state()
        elif is_quiz_answer_correct(answer_text, game['correct_answer']):
            game['score'] += 1
            response = f"啱咗！分數：{game['score']}" if lang == 'zh-HK' else f"Correct! Score: {game['score']}"
        else:
            if lang == 'zh-HK':
                response = f"唔啱呀，答案係{game['correct_answer']}。分數：{game['score']}"
            else:
                response = f"Incorrect. The answer was {game['correct_answer']}. Score: {game['score']}"

        if answer_text_lower not in answer_only_tokens and answer_text:
            game['current_index'] += 1
            if game['current_index'] == len(active_questions):
                if lang == 'zh-HK':
                    response += f"\n遊戲完成！你答啱咗{game['score']}條（總共{len(active_questions)}條）。叻叻！"
                else:
                    response += f"\nGame over! You successfully answered {game['score']} out of {len(active_questions)} questions correctly."
                game['is_game_mode'] = False
            else:
                q = active_questions[game['current_index']]
                game['current_question'] = q["question"]
                game['correct_answer'] = q["answer"]
                if lang == 'zh-HK':
                    response += f" 下一條問題：{q['question']}"
                else:
                    response += f" Next question: {q['question']}"
            _persist_game_state()
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

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > stt.MAX_TRANSCRIBE_UPLOAD_BYTES:
        return JSONResponse({"text": "", "error": "Audio file too large."}, status_code=413)
    if audio.content_type and not audio.content_type.startswith("audio/"):
        return JSONResponse({"text": "", "error": "Expected an audio file."}, status_code=415)

    language = (lang or get_lang(request) or "en").strip()
    lang_map = {
        "en": "en-US",
        "en-us": "en-US",
        "zh": "zh-HK",
        "zh-hk": "zh-HK",
        "zh_HK": "zh-HK",
    }
    language = lang_map.get(language.lower(), language)

    content = await audio.read()
    if not content:
        return JSONResponse({"text": "", "error": "Empty audio payload."}, status_code=400)
    if len(content) > stt.MAX_TRANSCRIBE_UPLOAD_BYTES:
        return JSONResponse({"text": "", "error": "Audio file too large."}, status_code=413)

    if stt.HF_API_KEY:
        try:
            text = await stt.transcribe_with_hf_whisper(content)
            if text:
                return JSONResponse({"text": text, "engine": stt.HF_WHISPER_MODEL})
            return JSONResponse(
                {"text": "", "error": get_text("no_speech_detected", get_lang(request))},
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
            {"text": "", "error": get_text("no_speech_detected", get_lang(request))},
            status_code=422,
        )
    except stt.sr.RequestError as e:
        logger.error(f"[STT] upstream request error: {e}")
        return JSONResponse(
            {"text": "", "error": get_text("error_network", get_lang(request))},
            status_code=503,
        )
    except Exception as e:
        logger.error(f"[STT] transcribe error: {e}")
        return JSONResponse(
            {"text": "", "error": get_text("error_voice", get_lang(request))},
            status_code=500,
        )


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
