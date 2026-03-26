import uuid

import pytest
from fastapi.testclient import TestClient

import run
from run import app


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
def _fake_db(monkeypatch):
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
    return state


def _new_user_email() -> str:
    return f"autotest_{uuid.uuid4().hex[:10]}@example.com"


def test_health_endpoints():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert "backend" in payload

        db_resp = client.get("/health/db")
        assert db_resp.status_code == 200
        db_payload = db_resp.json()
        assert db_payload["ok"] is True


def test_register_login_chat_and_reminders_flow():
    email = _new_user_email()
    password = "TestPass123!"

    with TestClient(app) as client:
        register_resp = client.post(
            "/register",
            data={
                "email": email,
                "password": password,
                "confirm_password": password,
            },
            follow_redirects=False,
        )
        assert register_resp.status_code == 303
        assert register_resp.headers["location"] == "/login"

        login_resp = client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        assert login_resp.headers["location"] == "/"
        session_cookie = login_resp.cookies.get("lt_session") or client.cookies.get("lt_session")
        assert session_cookie
        client.cookies.set("lt_session", session_cookie)

        home_resp = client.get("/", follow_redirects=False)
        assert home_resp.status_code == 200

        chat_resp = client.post("/get_response", data={"msg": "hello"})
        assert chat_resp.status_code == 200
        assert "response" in chat_resp.json()

        set_reminder_resp = client.post(
            "/get_response", data={"msg": "set reminder take medicine 09:00"}
        )
        assert set_reminder_resp.status_code == 200
        assert "Reminder set" in set_reminder_resp.json()["response"]

        reminders_resp = client.get("/get_reminders")
        assert reminders_resp.status_code == 200
        reminders = reminders_resp.json()["reminders"]
        assert any(r["label"] == "take medicine" for r in reminders)

        delete_reminder_resp = client.post(
            "/get_response", data={"msg": "delete reminder take medicine"}
        )
        assert delete_reminder_resp.status_code == 200
        assert "Deleted reminder" in delete_reminder_resp.json()["response"]


def test_quiz_flow():
    email = _new_user_email()
    password = "TestPass123!"

    with TestClient(app) as client:
        client.post(
            "/register",
            data={
                "email": email,
                "password": password,
                "confirm_password": password,
            },
            follow_redirects=False,
        )
        login_resp = client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        session_cookie = login_resp.cookies.get("lt_session") or client.cookies.get("lt_session")
        assert session_cookie
        client.cookies.set("lt_session", session_cookie)

        home_resp = client.get("/", follow_redirects=False)
        assert home_resp.status_code == 200

        start_resp = client.post("/get_response", data={"msg": "play game"})
        assert start_resp.status_code == 200
        assert "Let's play" in start_resp.json()["response"]

        answer_resp = client.post("/get_response", data={"msg": "paris"})
        assert answer_resp.status_code == 200
        assert "Score" in answer_resp.json()["response"]


def test_existing_user_can_login_without_reregister():
    email = _new_user_email()
    password = "TestPass123!"

    with TestClient(app) as client:
        first_register = client.post(
            "/register",
            data={
                "email": email,
                "password": password,
                "confirm_password": password,
            },
            follow_redirects=False,
        )
        assert first_register.status_code == 303

        duplicate_register = client.post(
            "/register",
            data={
                "email": email.upper(),
                "password": password,
                "confirm_password": password,
            },
            follow_redirects=True,
        )
        assert duplicate_register.status_code == 200
        assert "Email already exists" in duplicate_register.text or "電郵已存在" in duplicate_register.text

        logout_resp = client.get("/logout", follow_redirects=False)
        assert logout_resp.status_code == 303

        login_again = client.post(
            "/login",
            data={"email": email.upper(), "password": password},
            follow_redirects=False,
        )
        assert login_again.status_code == 303
        assert login_again.headers["location"] == "/"
