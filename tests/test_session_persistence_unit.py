from fastapi.testclient import TestClient

import run


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self._last = None

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())

        if "insert into users" in normalized:
            email, password, _ts = params
            if email in self.state["users"]:
                raise run.PgIntegrityError("duplicate")
            new_id = len(self.state["users"]) + 1
            self.state["users"][email] = {"id": new_id, "email": email, "password": password}
            self._last = None
            return

        if "select id, email, password from users where lower(email) = lower(%s)" in normalized:
            email = params[0]
            user = self.state["users"].get(email.lower())
            self._last = {"id": user["id"], "email": user["email"], "password": user["password"]} if user else None
            return

        if "update users set password = %s where id = %s" in normalized:
            hashed, user_id = params
            for row in self.state["users"].values():
                if row["id"] == user_id:
                    row["password"] = hashed
                    break
            self._last = None
            return

        if "update users set last_login = %s where id = %s" in normalized:
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

    def commit(self):
        return None

    def close(self):
        return None


def test_existing_user_can_login_without_reregister(monkeypatch):
    state = {"users": {}}

    monkeypatch.setattr(run, "ensure_db_initialized", lambda strict=False: True)
    monkeypatch.setattr(run, "get_db", lambda: _FakeConn(state))

    with TestClient(run.app) as client:
        register_resp = client.post(
            "/register",
            data={
                "email": "User@Test.com",
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
            },
            follow_redirects=False,
        )
        assert register_resp.status_code == 303
        assert register_resp.headers.get("location") == "/login"

        client.get("/logout", follow_redirects=False)

        login_resp = client.post(
            "/login",
            data={"email": "user@test.com", "password": "TestPass123!"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        assert login_resp.headers.get("location") == "/"
        assert "lt_session=" in login_resp.headers.get("set-cookie", "")
