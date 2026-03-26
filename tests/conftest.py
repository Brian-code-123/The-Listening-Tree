import os

import pytest

import run


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self._rows = []
        self._one = None
        self.rowcount = 0

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        self._rows = []
        self._one = None
        self.rowcount = 0

        if normalized == "select 1":
            self._one = {"?column?": 1}
            return

        if "insert into users" in normalized:
            email, password, created_at = params
            if email in self.state["users_by_email"]:
                raise run.PgIntegrityError("duplicate email")
            user_id = self.state["next_user_id"]
            self.state["next_user_id"] += 1
            user = {
                "id": user_id,
                "email": email,
                "password": password,
                "created_at": created_at,
                "last_login": None,
            }
            self.state["users_by_email"][email] = user
            self.state["users_by_id"][user_id] = user
            self.rowcount = 1
            return

        if "select id, email, password from users where lower(email) = lower(%s)" in normalized:
            email = params[0].lower()
            user = self.state["users_by_email"].get(email)
            self._one = {
                "id": user["id"],
                "email": user["email"],
                "password": user["password"],
            } if user else None
            return

        if "update users set password = %s where id = %s" in normalized:
            password, user_id = params
            user = self.state["users_by_id"].get(user_id)
            if user:
                user["password"] = password
                self.rowcount = 1
            return

        if "update users set last_login = %s where id = %s" in normalized:
            ts, user_id = params
            user = self.state["users_by_id"].get(user_id)
            if user:
                user["last_login"] = ts
                self.rowcount = 1
            return

        if "select pref_value from preferences" in normalized:
            self._one = None
            return

        if "insert into chat_history" in normalized:
            self.state["chat_history"].append(params)
            self.rowcount = 1
            return

        if "insert into reminders" in normalized:
            user_id, label, reminder_time, created_at = params
            self.state["reminders"].append(
                {
                    "user_id": user_id,
                    "label": label,
                    "reminder_time": reminder_time,
                    "is_active": True,
                    "created_at": created_at,
                }
            )
            self.rowcount = 1
            return

        if "delete from reminders where user_id = %s and label = %s" in normalized:
            user_id, label = params
            before = len(self.state["reminders"])
            self.state["reminders"] = [
                r
                for r in self.state["reminders"]
                if not (r["user_id"] == user_id and r["label"] == label)
            ]
            self.rowcount = before - len(self.state["reminders"])
            return

        if "select label, reminder_time, is_active from reminders" in normalized:
            user_id, _today = params
            self._rows = [
                {
                    "label": r["label"],
                    "reminder_time": r["reminder_time"],
                    "is_active": 1 if r["is_active"] else 0,
                }
                for r in self.state["reminders"]
                if r["user_id"] == user_id
            ]
            return

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return _FakeCursor(self.state)

    def commit(self):
        return None

    def close(self):
        return None


@pytest.fixture(autouse=True)
def fake_db_for_tests(monkeypatch):
    if os.environ.get("RUN_LIVE_DB") == "1":
        return

    state = {
        "next_user_id": 1,
        "users_by_email": {},
        "users_by_id": {},
        "reminders": [],
        "chat_history": [],
    }
    monkeypatch.setattr(run, "ensure_db_initialized", lambda strict=False: True)
    monkeypatch.setattr(run, "get_db", lambda: _FakeConn(state))
    run.user_game_states.clear()
    run.user_api_histories.clear()
