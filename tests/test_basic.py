import pytest
import uuid
from fastapi.testclient import TestClient
from run import app

client = TestClient(app)

def test_read_main():
    # Test if login page loads (unauthenticated)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text or "登入" in response.text

def test_api_status():
    # Test a simple API call if any exists or just root redirect
    response = client.get("/")
    assert response.status_code in [200, 302] # 302 if redirecting to login


def _new_user_email() -> str:
    return f"autotest_{uuid.uuid4().hex[:10]}@example.com"


def test_health_endpoints():
    with TestClient(app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert "backend" in payload

        db_resp = c.get("/health/db")
        assert db_resp.status_code == 200
        db_payload = db_resp.json()
        assert db_payload["ok"] is True


def test_register_login_chat_and_reminders_flow():
    email = _new_user_email()
    password = "TestPass123!"

    with TestClient(app) as c:
        register_resp = c.post(
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

        login_resp = c.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        assert login_resp.headers["location"] == "/"
        session_cookie = login_resp.cookies.get("lt_session") or c.cookies.get("lt_session")
        assert session_cookie
        c.cookies.set("lt_session", session_cookie)

        chat_resp = c.post("/get_response", data={"msg": "hello"})
        assert chat_resp.status_code == 200
        assert "response" in chat_resp.json()

        set_reminder_resp = c.post(
            "/get_response", data={"msg": "set reminder take medicine 09:00"}
        )
        assert set_reminder_resp.status_code == 200
        assert "Reminder set" in set_reminder_resp.json()["response"]

        reminders_resp = c.get("/get_reminders")
        assert reminders_resp.status_code == 200
        reminders = reminders_resp.json()["reminders"]
        assert any(r["label"] == "take medicine" for r in reminders)

        delete_reminder_resp = c.post(
            "/get_response", data={"msg": "delete reminder take medicine"}
        )
        assert delete_reminder_resp.status_code == 200
        assert "Deleted reminder" in delete_reminder_resp.json()["response"]


def test_quiz_flow():
    email = _new_user_email()
    password = "TestPass123!"

    with TestClient(app) as c:
        c.post(
            "/register",
            data={
                "email": email,
                "password": password,
                "confirm_password": password,
            },
            follow_redirects=False,
        )
        login_resp = c.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert login_resp.status_code == 303
        session_cookie = login_resp.cookies.get("lt_session") or c.cookies.get("lt_session")
        assert session_cookie
        c.cookies.set("lt_session", session_cookie)

        start_resp = c.post("/get_response", data={"msg": "play game"})
        assert start_resp.status_code == 200
        assert "Let's play" in start_resp.json()["response"]

        answer_resp = c.post("/get_response", data={"msg": "paris"})
        assert answer_resp.status_code == 200
        assert "Score" in answer_resp.json()["response"]
