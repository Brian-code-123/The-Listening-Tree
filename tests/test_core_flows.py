"""
Mermaid sequence diagram:
sequenceDiagram
    participant Tester
    participant API
    participant DB
    participant GameState
    Tester->>API: register/login and send reminder/chat commands
    API->>DB: create/read/update/delete reminder records
    API->>GameState: start and advance quiz state
    API-->>Tester: responses and state changes
"""

import uuid

from fastapi.testclient import TestClient

from run import app


def _new_user_email() -> str:
    return f"autotest_{uuid.uuid4().hex[:10]}@example.com"


def test_health_endpoints():
    with TestClient(app) as client:
        # /health is intentionally minimal for an unauthenticated caller —
        # no infra details (hostname, backend config, raw exception text).
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert "db_hostname" not in payload

        db_resp = client.get("/health/db")
        assert db_resp.status_code == 200
        db_payload = db_resp.json()
        assert db_payload["ok"] is True
        assert "db_hostname" not in db_payload


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
                "verification_code": "123456",
            },
            follow_redirects=False,
        )
        assert register_resp.status_code == 303
        assert register_resp.headers["location"] == "/"

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
                "verification_code": "123456",
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
                "verification_code": "123456",
            },
            follow_redirects=False,
        )
        assert first_register.status_code == 303
        assert first_register.headers["location"] == "/"

        duplicate_register = client.post(
            "/register",
            data={
                "email": email.upper(),
                "password": password,
                "confirm_password": password,
                "verification_code": "123456",
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
