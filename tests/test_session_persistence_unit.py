"""
Mermaid sequence diagram:
sequenceDiagram
    participant Tester
    participant Session
    participant FastAPI
    participant DB
    Tester->>FastAPI: create account and login
    FastAPI->>Session: persist lt_session cookie
    FastAPI->>DB: read/write preference and chat history rows
    FastAPI-->>Tester: preserved state across requests
"""

from fastapi.testclient import TestClient

from app.db import queries as db
from app.db import schema
from run import app


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self._last = None

    async def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())

        # Registration requires a verification_code — accept any code for
        # any email, matching the equivalent fake in tests/conftest.py.
        if "select id from email_verifications where lower(email) = lower(?) and code = ?" in normalized:
            self._last = {"id": 1}
            return
        if "update email_verifications set used = true where id = ?" in normalized:
            self._last = None
            return

        if "update users set consent_at" in normalized:
            return

        if "insert into users" in normalized:
            email, password, _ts = params
            if email in self.state["users"]:
                raise db.PgIntegrityError("duplicate")
            new_id = len(self.state["users"]) + 1
            self.state["users"][email] = {
                "id": new_id,
                "email": email,
                "password": password,
                "session_version": 0,
                "is_active": True,
            }
            self._last = None
            return

        if "select id, email, password, session_version, is_active from users where lower(email) = lower(?)" in normalized:
            email = params[0]
            user = self.state["users"].get(email.lower())
            self._last = dict(user) if user else None
            return

        if "select session_version, is_active from users where id = ?" in normalized:
            user = next((u for u in self.state["users"].values() if u["id"] == params[0]), None)
            self._last = {"session_version": user["session_version"], "is_active": user["is_active"]} if user else None
            return

        if "select id, email, password from users where lower(email) = lower(?)" in normalized:
            email = params[0]
            user = self.state["users"].get(email.lower())
            self._last = {"id": user["id"], "email": user["email"], "password": user["password"]} if user else None
            return

        if "update users set password = ? where id = ?" in normalized:
            hashed, user_id = params
            for row in self.state["users"].values():
                if row["id"] == user_id:
                    row["password"] = hashed
                    break
            self._last = None
            return

        if "update users set last_login" in normalized:
            self._last = None
            return


        if "select pref_value from preferences" in normalized:
            self._last = None
            return

        self._last = None

    def fetchone(self):
        return self._last

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return _FakeCursor(self.state)

    async def commit(self):
        return None

    async def close(self):
        return None


def test_existing_user_can_login_without_reregister(monkeypatch):
    state = {"users": {}}

    async def _fake_ensure_db_initialized(strict=False):
        return True

    async def _fake_get_db():
        return _FakeConn(state)

    monkeypatch.setattr(schema, "ensure_db_initialized", _fake_ensure_db_initialized)
    monkeypatch.setattr(db, "get_db", _fake_get_db)

    with TestClient(app) as client:
        register_resp = client.post(
            "/register",
            data={
                "email": "User@Test.com",
                "password": "TestPass123!",
                "confirm_password": "TestPass123!", "consent": "true",
                "verification_code": "123456",
            },
            follow_redirects=False,
        )
        assert register_resp.status_code == 303
        assert register_resp.headers.get("location") == "/"

        client.post("/logout", follow_redirects=False)

        login_resp = client.post(
            "/login",
            data={"email": "user@test.com", "password": "TestPass123!"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        assert login_resp.headers.get("location") == "/"
        assert "lt_session=" in login_resp.headers.get("set-cookie", "")
