"""Daily reminders round-trip their repeat type; a returning user gets a check-in."""
import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.routers import conversations as conv
from run import app


class _Cursor:
    """Just enough cursor for load_conversation_messages: one SELECT, records INSERTs."""

    def __init__(self, rows):
        self.rows, self.inserted = rows, []

    async def execute(self, query, params=()):
        if query.lstrip().upper().startswith("INSERT"):
            self.inserted.append(params)

    def fetchall(self):
        return self.rows


class _Conn:
    async def commit(self):
        pass


def _row(hours_ago, message, is_bot=True):
    ts = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    return {"id": 1, "user_id": 7, "timestamp": ts, "is_bot": is_bot, "message": message}


def _load(rows, lang="en", checkin=True):
    cur = _Cursor(rows)
    history = asyncio.run(conv.load_conversation_messages(cur, _Conn(), 1, lang, checkin=checkin))
    return history, cur.inserted


def test_checkin_added_after_long_gap():
    history, inserted = _load([_row(7, "Sure, take care!")])
    assert history[-1]["sender"] == "bot" and history[-1]["message"] in conv._all_checkins()
    assert len(inserted) == 1 and inserted[0][0] == 7


def test_no_checkin_for_recent_chat_or_after_checkin():
    assert _load([_row(1, "hi")])[1] == []
    assert _load([_row(9, conv.get_text("checkin_morning", "en"))])[1] == []


def test_no_checkin_when_browsing_old_conversation():
    assert _load([_row(500, "bye")], checkin=False)[1] == []


def test_checkin_is_localised():
    history, _ = _load([_row(8, "好呀")], lang="zh-HK")
    assert history[-1]["message"] in conv._all_checkins() and "呀" in history[-1]["message"]


def test_daily_reminder_repeat_roundtrip():
    with TestClient(app) as client:
        from tests.integration.test_reminders_crud import _new_user_email
        email, pw = _new_user_email(), "TestPass123!"
        client.post("/register", data={"email": email, "password": pw, "confirm_password": pw, "verification_code": "123456"}, follow_redirects=False)
        client.post("/login", data={"email": email, "password": pw}, follow_redirects=False)
        assert client.post("/reminders", data={"label": "walk", "time": "08:00", "repeat": "daily"}).json()["repeat"] == "daily"
        client.post("/reminders", data={"label": "pill", "time": "09:00"})
        assert client.post("/reminders", data={"label": "x", "time": "09:00", "repeat": "weekly"}).status_code == 400
        got = {r["label"]: r["repeat"] for r in client.get("/get_reminders").json()["reminders"]}
        assert got == {"walk": "daily", "pill": "once"}
