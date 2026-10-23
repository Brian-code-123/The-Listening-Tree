"""Pre-check for messages that need a person, not the language model.

A crisis or medical emergency gets a fixed, reviewed reply with the real phone
numbers; the model is never asked. Scam talk still goes to the model, with an
extra warning added to the prompt. Matching is plain keyword rules, kept
deliberately narrow: a false alarm costs one extra caring message, a miss costs
far more, but a rule that fires on everyday idioms (「笑死我」, 「死線」) would
teach people to ignore it.
"""
import re
from dataclasses import dataclass
from typing import Literal, Optional

Kind = Literal["crisis", "emergency", "scam"]


@dataclass(frozen=True)
class SafetyResult:
    kind: Optional[Kind] = None
    reply: Optional[str] = None


# Everyday idioms that contain a trigger word. Removed before matching.
_IDIOMS = re.compile(
    r"(笑|嚇|悶|餓|攰|熱|凍|嬲|煩|激|慘|肉赤|忙|趕|唔想死你)死(我|人|咗|了)?|想死你|死線|死死[哋地]|"
    r"to die for|dying to|dead tired|dying of (laughter|boredom)|kill(ing)? time|killed it|"
    r"die[- ]hard|my phone died|battery died",
    re.IGNORECASE,
)

_CRISIS = re.compile(
    r"想死|唔想活|不想活|想自殺|自殺|輕生|結束(自己)?(嘅)?生命|了結(自己)?|跳樓|割脈|"
    r"suicid|kill myself|end my (own )?life|want to die|wanna die|don'?t want to (live|be alive)|"
    r"better off dead|take my own life",
    re.IGNORECASE,
)

_EMERGENCY = re.compile(
    r"(胸口|心口|心臟|心).{0,3}(好|很|非常|太)?.{0,2}(痛|绞|絞|翳|緊)|呼吸困難|透唔到氣|喘唔到氣|唔夠氣|"
    r"中風|半身(麻|不遂)|面歪|口歪|突然(暈|昏)|暈倒|昏迷|跌低.{0,4}(起唔到|郁唔到)|起唔到身|大量(出血|流血)|嘔血|"
    r"chest (pain|tightness|pressure)|can'?t breathe|cannot breathe|trouble breathing|short of breath|"
    r"stroke|face (is )?droop|slurred speech|passed out|fainted|unconscious|fell and can'?t get up|bleeding (heavily|badly)",
    re.IGNORECASE,
)

_SCAM = re.compile(
    r"轉(帳|賬|數)|過(帳|數)|領獎|中獎|匯款|入(數|錢)|禮品卡|點數卡|假冒|自稱.{0,6}(警|官|銀行|公安)|"
    r"安全戶口|解凍|驗證碼.{0,6}(畀|給|俾)|"
    r"transfer (money|funds)|send (money|cash)|gift ?card|you('ve| have)? won|prize|wire (money|funds)|"
    r"(police|bank|government|tax).{0,25}(call|called|phone|asked)|safe account|verification code",
    re.IGNORECASE,
)

REPLIES = {
    ("crisis", "en"): (
        "I'm really glad you told me, and I'm worried about you. You don't have to go through this alone. "
        "Please call the Samaritans, free and private, 24 hours a day: 2896 0000. "
        "If you are in danger right now, call 999 or tell someone near you straight away."
    ),
    ("crisis", "zh-HK"): (
        "多謝你同我講，我好擔心你。你唔需要自己一個人捱。"
        "請即刻打撒瑪利亞防止自殺會熱線，24 小時免費、保密：2896 0000。"
        "如果你而家有危險，請打 999，或者即刻搵身邊嘅人幫手。"
    ),
    ("emergency", "en"): (
        "This sounds serious. Please call 999 now, or ask someone near you to call. "
        "Do not wait to see if it gets better. If you can, unlock the door and sit or lie down while help comes."
    ),
    ("emergency", "zh-HK"): (
        "聽落好嚴重。請即刻打 999，或者叫身邊嘅人幫你打。"
        "唔好等，睇下會唔會好返。如果做得到，將門打開，坐低或者瞓低等人嚟。"
    ),
}

_SCAM_HINT = {
    "en": "The user's message may involve a scam (money transfer, prize, someone claiming to be police or a bank). "
          "Gently warn them not to send money or share codes, to hang up and talk to family first, "
          "and that the Hong Kong Police Anti-Deception Coordination Centre line is 18222.",
    "zh-HK": "用戶嘅訊息可能同騙案有關（轉帳、中獎、有人自稱警察或銀行）。"
             "請溫和提醒佢唔好轉帳、唔好講出驗證碼，先掛線同家人商量，亦可以打防騙易熱線 18222。",
}


def scam_hint(lang: str) -> str:
    return _SCAM_HINT["zh-HK" if lang == "zh-HK" else "en"]


def check_message(text: str, lang: str) -> SafetyResult:
    cleaned = _IDIOMS.sub(" ", text or "")
    key = "zh-HK" if lang == "zh-HK" else "en"
    if _CRISIS.search(cleaned):
        return SafetyResult("crisis", REPLIES[("crisis", key)])
    if _EMERGENCY.search(cleaned):
        return SafetyResult("emergency", REPLIES[("emergency", key)])
    if _SCAM.search(cleaned):
        return SafetyResult("scam", None)
    return SafetyResult()
