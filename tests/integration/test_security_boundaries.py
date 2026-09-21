import os

import pytest
from fastapi.testclient import TestClient

from run import app
from tests.integration.helpers import PASSWORD, register_and_login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("RUN_LIVE_DB") != "1", reason="needs RUN_LIVE_DB=1 and a local database"),
]


def _new_conversation(client) -> int:
    return client.post("/conversations/new").json()["conversation_id"]


def _switch_user(client, cookies):
    client.cookies.clear()
    client.cookies.update(cookies)


def test_another_user_cannot_read_or_change_a_conversation():
    # One TestClient (the app has a single global DB pool); swap cookie jars.
    with TestClient(app) as client:
        register_and_login(client)
        cid = _new_conversation(client)
        client.post("/get_response", data={"msg": "my private note", "conversation_id": cid})
        client.post(f"/conversations/{cid}/title", data={"title": "Owner title"})
        owner = dict(client.cookies)

        client.cookies.clear()
        register_and_login(client)  # a second, unrelated user

        messages = client.get(f"/conversations/{cid}/messages")
        assert messages.status_code == 404
        assert "my private note" not in messages.text
        assert client.post(f"/conversations/{cid}/pin").status_code == 404
        assert client.post(f"/conversations/{cid}/tag", data={"tag": "family"}).status_code == 404
        assert client.post(f"/conversations/{cid}/title", data={"title": "hijacked"}).status_code == 404

        _switch_user(client, owner)
        row = next(c for c in client.get("/conversations").json()["conversations"] if c["id"] == cid)
        assert row["title"] == "Owner title" and row["pinned"] is False and row["tag"] is None


def test_posting_with_another_users_conversation_id_does_not_write_into_it():
    with TestClient(app) as client:
        register_and_login(client)
        cid = _new_conversation(client)
        owner = dict(client.cookies)

        client.cookies.clear()
        register_and_login(client)
        client.post("/get_response", data={"msg": "intruder message", "conversation_id": cid})

        _switch_user(client, owner)
        history = client.get(f"/conversations/{cid}/messages").json()["history"]
        assert all("intruder message" not in item["message"] for item in history)


def test_logged_out_requests_get_no_data():
    with TestClient(app) as anon:
        assert anon.get("/get_reminders").json() == {"reminders": []}
        assert anon.get("/conversations").json() == {"conversations": []}
        assert anon.get("/conversations/1/messages").status_code == 401
        assert anon.post("/get_response", data={"msg": "hi"}).status_code == 401
        assert anon.post("/conversations/new").status_code == 401


@pytest.mark.parametrize("email", ["' OR '1'='1", "admin'--", "x@example.com' OR 1=1 --", '"; DROP TABLE users; --'])
def test_sql_injection_shaped_login_is_just_a_failed_login(email):
    with TestClient(app) as client:
        # The login endpoint answers a bad login with 200 and {"success": false}.
        resp = client.post(
            "/auth/login",
            data={"email": email, "password": "' OR '1'='1"},
            headers={"Accept": "application/json"},
        )
        assert resp.json()["success"] is False
        assert client.get("/me").status_code == 401  # no session was created

        # The users table survived and normal registration/login still works.
        register_and_login(client)
        assert client.get("/me").json()["authenticated"] is True


def test_session_cookie_is_httponly_and_samesite_lax():
    with TestClient(app) as client:
        email, _ = register_and_login(client)
        resp = client.post("/login", data={"email": email, "password": PASSWORD}, follow_redirects=False)
        cookie = resp.headers.get("set-cookie", "").lower()
        assert "lt_session=" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
