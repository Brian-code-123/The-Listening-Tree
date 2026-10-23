"""Zhipu AI (智谱AI) chat completion — the warm elderly-companion persona."""
import json
import logging
import os
import random
from typing import Optional

import httpx

from app.db import queries as db

ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.environ.get("ZHIPU_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL = os.environ.get("ZHIPU_MODEL") or "glm-4-flash"
# How many recent chat_history rows (~half that many round-trips) are sent
# to the LLM as conversation memory. Read from chat_history rather than an
# in-memory dict so it survives restarts and is shared across serverless
# instances instead of silently resetting.
CHAT_CONTEXT_MESSAGES = int(os.environ.get("CHAT_CONTEXT_MESSAGES") or 20)

logger = logging.getLogger(__name__)

if ZHIPU_API_KEY:
    logger.info(f"[AI] {ZHIPU_MODEL} configured (Zhipu AI)")
else:
    logger.warning("[AI] ZHIPU_API_KEY not set — using warm fallback responses")

# System prompt — Cantonese elderly companion (Chinese)
# Guides the LLM to reply in warm, patient Cantonese with simple vocabulary.
WARM_SYSTEM_PROMPT_ZH = """你係一個有禮貌、溫柔、有耐心嘅陪伴者，專門陪老人家傾偈。

你嘅講嘢風格：
- 你一定要用廣東話（粵語）回答，唔好用普通話！
- 語氣溫柔、有禮貌，保持得體嘅距離感，唔好扮到好熟或者好親暱
- 唔好自稱係佢孫仔女，唔好用過度親暱嘅稱呼
- 唔知道用戶性別，就唔好用任何性別化或者戲曲式稱謂（例如「阿公」「阿婆」「老倌」），亦唔好同時列出多個稱呼選項俾用戶揀，需要稱呼就用中性字眼（例如「你」）或者索性唔加稱呼
- 講嘢簡單易明，唔用複雜詞語
- 適時表達關心：「你今日點呀？」「食咗飯未？」「有冇瞓得好？」
- 鼓勵說話要適可而止，唔好誇張或者重複咁講
- 如果老人家講唔清楚或重複問題，要非常有耐心，唔好顯出唔耐煩
- 先實質回應用戶講嘅內容（例如：畀意見、表達理解、提供安慰或者建議），唔好淨係反問一句就算，唔好將反問當做預設答法去迴避思考
  - 講身體不適：要有實際反應，例如建議留意情況、休息、或者提醒睇醫生
  - 講情緒或者掛住人：要先回應個感受（理解佢、安慰佢），先至可以順便問多句
- 淨係喺真係需要更多資訊先可以幫到手嘅時候先問返問題，唔好逢句都咁做
- 回覆保持簡短（2-4句），易讀易明

重要：直接回答用戶嘅問題，唔好顯示你嘅思考過程或分析步驟。
重要：你一定要用廣東話回答，唔好用普通話或者書面語。

安全規則：
- 唔好做診斷，亦唔好講藥物劑量；有健康擔心就建議睇醫生或藥劑師。
- 如果用戶可能有危險或者緊急情況，叫佢即刻打 999。
- 唔好問用戶要密碼、銀行資料或者驗證碼，亦唔好重複佢講過嘅呢啲資料。

記住：你嘅目標係用禮貌、溫柔嘅態度陪伴老人家，唔係扮熟或者浮誇。"""

# System prompt — English elderly companion
# Guides the LLM to reply in warm, patient English with simple vocabulary.
WARM_SYSTEM_PROMPT_EN = """You are a polite, gentle, and patient companion who chats with elderly people.

Your speaking style:
- Warm but respectful tone — polite and courteous, not overly familiar or exaggerated
- Do not call yourself their grandchild or use overly intimate terms of address
- Gender is unknown — never use gendered forms of address (e.g. "sir", "madam", "grandpa", "grandma") and never offer multiple address options; use neutral "you" or no form of address at all
- Use simple, easy-to-understand language
- Express concern where appropriate: "How are you today?" "Have you eaten?" "Did you sleep well?"
- Keep encouragement measured and sincere — avoid gushing or repetitive praise
- Be very patient if the user is unclear or repeats questions — never show impatience
- Actually respond to the substance of what the user said (give advice, show understanding, offer comfort or a concrete suggestion) — do not default to bouncing a question back instead of engaging
  - Physical discomfort: react concretely — suggest resting, monitoring the symptom, or seeing a doctor if needed
  - Emotional topics or missing someone: acknowledge the feeling first before adding any follow-up question
- Only ask a follow-up question when you genuinely need more information to help — don't do it as a reflex on every message
- Keep responses short (2-4 sentences), easy to read and understand

IMPORTANT: Answer the user's questions directly without showing your reasoning process or analysis steps.

Safety rules:
- Never diagnose, and never name medicine doses. For health worries, suggest seeing a doctor or pharmacist.
- If the user may be in danger or in an emergency, tell them to call 999.
- Never ask the user for, or repeat back, passwords, bank details or verification codes.

Remember: Your goal is to make elderly people feel respected, cared for, and at ease — not overly familiar."""

# Warm fallback responses — returned when the LLM API key is missing or
# the API call fails.  Keeps the UX friendly even under degraded mode.
WARM_FALLBACK_ZH = [
    "你好，很高興與你相遇。今天過得還好嗎？😊",
    "不必擔心，無論什麼心事，都可以慢慢說給我聽。",
    "你講嘅嘢我都有留心聽緊。",
    "好的，請繼續說吧，我很樂意聆聽。",
    "記得好好照顧自己，吃得飽、睡得好。😊",
    "謝謝你願意與我分享。",
    "我明白你的心情，請記住，你從來都不是一個人。",
    "聽你咁講，我都替你開心。",
    "今天天氣如何？記得注意保暖，照顧好自己。",
    "昨晚睡得安穩嗎？好好休息，身體才會健康。",
]

WARM_FALLBACK_EN = [
    "That's interesting, thank you for sharing. 😊",
    "I understand what you mean. How does that make you feel?",
    "Thank you for sharing that with me.",
    "That sounds lovely. What else have you been up to today?",
    "I appreciate you telling me about that. Is there anything else on your mind?",
    "Good to hear from you. What else would you like to talk about?",
    "I hear you, and I'm glad you told me. 😊",
]


def _fallback_for(lang: str) -> list:
    return WARM_FALLBACK_ZH if lang == 'zh-HK' else WARM_FALLBACK_EN


async def build_ai_messages(cursor, user_input: str, user_id: int, lang: str = 'en', display_name: Optional[str] = None, conversation_id: Optional[int] = None, extra_system: Optional[str] = None) -> list:
    """The message list sent to the model: system prompt, recent history, the new message."""
    system_prompt = WARM_SYSTEM_PROMPT_ZH if lang == 'zh-HK' else WARM_SYSTEM_PROMPT_EN

    # The name is already cleaned when written in /profile/name, but it goes into
    # the system prompt, so flatten it again here: a leftover newline would let a
    # name carry its own instructions.
    display_name = " ".join((display_name or "").split())[:30] or None
    if display_name:
        name_hint = (
            f"用戶嘅名叫{display_name}，可以間唔中親切噉叫返佢個名。"
            if lang == 'zh-HK'
            else f"The user's name is {display_name}; address them by name occasionally."
        )
        system_prompt = f"{system_prompt}\n\n{name_hint}"
    if extra_system:
        system_prompt = f"{system_prompt}\n\n{extra_system}"

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_id is not None:
        # Conversation memory comes from chat_history itself instead of an
        # in-memory dict, so it survives restarts and is consistent across
        # serverless instances. The caller already inserted the current user
        # message into this conversation before calling us, so it's the
        # newest row here — fetch one extra and drop it to get the *prior*
        # turns only.
        await db.db_execute(
            cursor,
            """
            SELECT is_bot, message FROM chat_history
            WHERE conversation_id = ? AND is_deleted = FALSE
            ORDER BY id DESC LIMIT ?
            """,
            (conversation_id, CHAT_CONTEXT_MESSAGES + 1),
        )
        history_rows = cursor.fetchall()[1:]
        history_rows.reverse()
        messages.extend(
            {"role": "assistant" if row["is_bot"] else "user", "content": row["message"]}
            for row in history_rows
        )

    messages.append({"role": "user", "content": user_input})
    return messages


def _payload(messages: list, stream: bool = False) -> dict:
    payload = {
        "model": ZHIPU_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 512,
    }
    if stream:
        payload["stream"] = True
    return payload


def _headers() -> dict:
    return {"Authorization": f"Bearer {ZHIPU_API_KEY}", "Content-Type": "application/json"}


async def call_ai(cursor, user_input: str, user_id: int, lang: str = 'en', display_name: Optional[str] = None, conversation_id: Optional[int] = None, extra_system: Optional[str] = None):
    """Call Zhipu AI (智谱AI) for warm elderly conversation."""
    fallback = _fallback_for(lang)
    if not ZHIPU_API_KEY:
        return random.choice(fallback)

    messages = await build_ai_messages(cursor, user_input, user_id, lang, display_name, conversation_id, extra_system)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{ZHIPU_BASE_URL}/chat/completions", json=_payload(messages), headers=_headers())
            resp.raise_for_status()
            result = resp.json()

        message = result.get("choices", [{}])[0].get("message", {})
        reply = message.get("content", "")

        if reply.strip():
            return reply
        else:
            raise ValueError("Empty response from API")

    except Exception as e:
        logger.error(f"[AI] Error calling Zhipu ({lang}): {e}")
        return random.choice(fallback)


# The reply is shown as it is written, so the user sees the first words after the
# model's time-to-first-token (under a second) instead of waiting for all of it
# (3 to 5 seconds). The model decodes at roughly 20 tokens a second whichever way
# it is asked for; streaming changes what the user perceives, not the total.
STREAM_FIRST_BYTE_TIMEOUT = 15  # seconds to wait for the first words before giving up
STREAM_READ_TIMEOUT = 30  # seconds of silence mid-reply before giving up


async def stream_ai(messages: list, lang: str = 'en'):
    """Yield the reply in pieces. Never raises: if the model cannot start, one
    warm fallback line is yielded instead; if it breaks mid-reply, what was
    already sent stands."""
    fallback = _fallback_for(lang)
    if not ZHIPU_API_KEY:
        yield random.choice(fallback)
        return

    sent_any = False
    try:
        timeout = httpx.Timeout(STREAM_READ_TIMEOUT, connect=STREAM_FIRST_BYTE_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{ZHIPU_BASE_URL}/chat/completions", json=_payload(messages, stream=True), headers=_headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        piece = json.loads(data)["choices"][0]["delta"].get("content") or ""
                    except (ValueError, KeyError, IndexError):
                        continue
                    if piece:
                        sent_any = True
                        yield piece
        if not sent_any:
            raise ValueError("Empty response from API")
    except Exception as e:
        logger.error(f"[AI] Error streaming from Zhipu ({lang}): {type(e).__name__}: {e}")
        if not sent_any:
            yield random.choice(fallback)
