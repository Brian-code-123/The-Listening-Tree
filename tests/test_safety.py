import pytest

from app.services import ai
from app.services.safety import check_message


@pytest.mark.parametrize("text,lang,kind", [
    ("我想死", "zh-HK", "crisis"),
    ("I want to end my life", "en", "crisis"),
    ("我唔想活喇", "zh-HK", "crisis"),
    ("胸口好痛", "zh-HK", "emergency"),
    ("I have chest pain", "en", "emergency"),
    ("我中風", "zh-HK", "emergency"),
    ("有人叫我轉帳領獎", "zh-HK", "scam"),
    ("a man on the phone says send money or gift cards", "en", "scam"),
])
def test_true_positives(text, lang, kind):
    assert check_message(text, lang).kind == kind


@pytest.mark.parametrize("text,lang", [
    ("my heart is happy today", "en"),
    ("笑死我喇", "zh-HK"),
    ("我想死你", "zh-HK"),
    ("今日好熱，熱死人", "zh-HK"),
    ("死線快到", "zh-HK"),
    ("I'm dying to see my grandson", "en"),
    ("this soup is to die for", "en"),
    ("what's the weather", "en"),
])
def test_everyday_words_do_not_trigger(text, lang):
    assert check_message(text, lang).kind is None


def test_replies_carry_the_real_numbers():
    en, zh = check_message("I want to die", "en").reply, check_message("我想死", "zh-HK").reply
    assert "2896 0000" in en and "999" in en
    assert "2896 0000" in zh and "999" in zh
    assert "999" in check_message("chest pain", "en").reply
    assert check_message("轉帳", "zh-HK").reply is None  # scam goes on to the model


def test_prompts_carry_the_safety_rules():
    assert "never diagnose" in ai.WARM_SYSTEM_PROMPT_EN.lower() and "999" in ai.WARM_SYSTEM_PROMPT_EN
    assert "999" in ai.WARM_SYSTEM_PROMPT_ZH and "診斷" in ai.WARM_SYSTEM_PROMPT_ZH
