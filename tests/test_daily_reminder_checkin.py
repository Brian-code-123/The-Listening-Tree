"""Daily reminders round-trip their repeat type; a returning user gets a check-in."""
import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.routers import conversations as conv
from run import app

GREETING = conv.get_text("checkin_morning", "en")


class _Cursor:
    """Just enough cursor for load_conversation_messages: the history SELECT,
    the MAX(timestamp) SELECT (via fetchone), and recorded INSERTs."""

    def __init__(self, rows, last_user_ts):
        self.rows, self.last_user_ts, self.inserted = rows, last_user_ts, []

    async def execute(self, query, params=()):
        if query.lstrip().upper().startswith("INSERT"):
            self.inserted.append(params)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return {"last_ts": self.last_user_ts}


class _Conn:
    async def commit(self):
        pass


def _ts(hours_ago):
    return (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def _row(hours_ago, message, is_bot=True):
    return {"id": 1, "user_id": 7, "timestamp": _ts(hours_ago), "is_bot": is_bot, "message": message}


def _load(rows, user_hours_ago, lang="en", checkin=True):
    """user_hours_ago: age of the user's latest message in ANY conversation (None = never)."""
    last_user_ts = None if user_hours_ago is None else _ts(user_hours_ago)
    cur = _Cursor(rows, last_user_ts)
    history = asyncio.run(conv.load_conversation_messages(cur, _Conn(), 1, lang, checkin=checkin))
    return history, cur.inserted


def test_should_checkin_decision_table():
    # (last_user_hours, last_row_message, last_row_hours) -> expected
    cases = {
        "away 7h": ((7, "bye", 7), True),
        "recent chat 1h": ((1, "bye", 1), False),
        "just under the 6h gap": ((5.9, "bye", 5.9), False),
        "just over the 6h gap": ((6.1, "bye", 6.1), True),
        "greeted 2h ago, user away 9h": ((9, GREETING, 2), False),
        "stale greeting 9h old, user away 20h": ((20, GREETING, 9), True),
        "active in another conversation 0.2h ago, this one is 500h old": ((0.2, "bye", 500), False),
        "user never wrote": ((None, "Hello", 1), False),
    }
    for name, (args, expected) in cases.items():
        assert conv._should_checkin(*args) is expected, name


def test_checkin_added_after_long_gap():
    rows = [_row(7, "hi", is_bot=False), _row(7, "Sure, take care!")]
    history, inserted = _load(rows, user_hours_ago=7)
    assert history[-1]["sender"] == "bot" and history[-1]["message"] in conv._all_checkins()
    assert len(inserted) == 1 and inserted[0][0] == 7


def test_no_checkin_when_user_was_active_in_another_conversation():
    rows = [_row(500, "hi", is_bot=False), _row(500, "old pinned reply")]
    history, inserted = _load(rows, user_hours_ago=0.2)
    assert inserted == [] and history[-1]["message"] == "old pinned reply"


def test_no_checkin_when_browsing_old_conversation():
    rows = [_row(500, "hi", is_bot=False), _row(500, "bye")]
    assert _load(rows, user_hours_ago=500, checkin=False)[1] == []


def test_checkin_is_localised():
    rows = [_row(8, "你好", is_bot=False), _row(8, "好呀")]
    history, _ = _load(rows, user_hours_ago=8, lang="zh-HK")
    assert history[-1]["message"] in conv._all_checkins() and "呀" in history[-1]["message"]


def test_daily_reminder_repeat_roundtrip():
    with TestClient(app) as client:
        from tests.integration.helpers import new_user_email
        email, pw = new_user_email(), "TestPass123!"
        client.post("/register", data={"email": email, "password": pw, "confirm_password": pw, "verification_code": "123456"}, follow_redirects=False)
        client.post("/login", data={"email": email, "password": pw}, follow_redirects=False)
        assert client.post("/reminders", data={"label": "walk", "time": "08:00", "repeat": "daily"}).json()["repeat"] == "daily"
        client.post("/reminders", data={"label": "pill", "time": "09:00"})
        assert client.post("/reminders", data={"label": "x", "time": "09:00", "repeat": "weekly"}).status_code == 400
        got = {r["label"]: r["repeat"] for r in client.get("/get_reminders").json()["reminders"]}
        assert got == {"walk": "daily", "pill": "once"}


def test_split_repeat_strips_daily_word():
    from app.routers.chat import _split_repeat

    assert _split_repeat("daily bp meds") == ("bp meds", "daily")
    assert _split_repeat("bp meds every day") == ("bp meds", "daily")
    assert _split_repeat("每日 食藥") == ("食藥", "daily")
    assert _split_repeat("食藥 每天") == ("食藥", "daily")
    assert _split_repeat("bp meds") == ("bp meds", "once")
    assert _split_repeat("daily") == ("daily", "once")  # nothing left to remind about
    assert _split_repeat("dailyroutine") == ("dailyroutine", "once")


def test_chat_command_creates_daily_reminder():
    with TestClient(app) as client:
        from tests.integration.helpers import new_user_email
        email, pw = new_user_email(), "TestPass123!"
        client.post("/register", data={"email": email, "password": pw, "confirm_password": pw, "verification_code": "123456"}, follow_redirects=False)
        client.post("/login", data={"email": email, "password": pw}, follow_redirects=False)
        reply = client.post("/get_response", data={"msg": "set reminder daily bp meds 08:00"}).json()["response"]
        assert reply == "Daily reminder set: bp meds every day at 08:00"
        client.post("/get_response", data={"msg": "設置提醒 每日 食藥 09:00"})
        got = {r["label"]: r["repeat"] for r in client.get("/get_reminders").json()["reminders"]}
        assert got == {"bp meds": "daily", "食藥": "daily"}
