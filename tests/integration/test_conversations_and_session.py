import pytest
from fastapi.testclient import TestClient

from run import app
from tests.integration.helpers import register_and_login

pytestmark = pytest.mark.integration


def _new_conversation(client) -> int:
    resp = client.post("/conversations/new")
    assert resp.status_code == 200
    return resp.json()["conversation_id"]


def test_delete_conversation_is_soft_and_a_repeat_delete_is_404():
    with TestClient(app) as client:
        register_and_login(client)
        cid = _new_conversation(client)

        first = client.delete(f"/conversations/{cid}")
        assert first.status_code == 200
        assert first.json() == {"deleted": True}

        assert client.delete(f"/conversations/{cid}").status_code == 404
        listed = client.get("/conversations").json()["conversations"]
        assert all(c["id"] != cid for c in listed)


def test_delete_conversation_of_another_user_is_404_and_it_survives():
    # One TestClient only: the app has a single global DB pool, so two clients
    # open at once attach to different event loops. Swap cookie jars instead.
    with TestClient(app) as client:
        register_and_login(client)
        cid = _new_conversation(client)
        owner_cookies = dict(client.cookies)

        client.cookies.clear()
        register_and_login(client)  # a second, unrelated user
        assert client.delete(f"/conversations/{cid}").status_code == 404

        client.cookies.clear()
        client.cookies.update(owner_cookies)
        assert any(c["id"] == cid for c in client.get("/conversations").json()["conversations"])


def test_delete_conversation_requires_login_and_unknown_id_is_404():
    with TestClient(app) as anon:
        assert anon.delete("/conversations/1").status_code == 401
    with TestClient(app) as client:
        register_and_login(client)
        assert client.delete("/conversations/999999999").status_code == 404


def test_pin_tag_and_title_round_trip():
    with TestClient(app) as client:
        register_and_login(client)
        cid = _new_conversation(client)

        assert client.post(f"/conversations/{cid}/pin").json()["pinned"] is True
        assert client.post(f"/conversations/{cid}/pin").json()["pinned"] is False
        assert client.post(f"/conversations/{cid}/title", data={"title": "Renamed"}).json()["title"] == "Renamed"
        assert client.post(f"/conversations/{cid}/tag", data={"tag": "family"}).json()["tag"] == "family"

        row = next(c for c in client.get("/conversations").json()["conversations"] if c["id"] == cid)
        assert row["title"] == "Renamed" and row["tag"] == "family"


def test_conversations_are_scoped_to_the_session_language():
    with TestClient(app) as client:
        register_and_login(client)
        cid = _new_conversation(client)  # created while the session language is en

        client.get("/set_language/zh-HK", follow_redirects=False)
        assert all(c["id"] != cid for c in client.get("/conversations").json()["conversations"])

        client.get("/set_language/en", follow_redirects=False)
        assert any(c["id"] == cid for c in client.get("/conversations").json()["conversations"])


def test_me_reflects_login_state_and_the_session_language_even_when_logged_out():
    with TestClient(app) as client:
        anon = client.get("/me")
        assert anon.status_code == 401
        assert anon.json() == {"authenticated": False, "lang": "en"}

        # A logged-out visitor's language choice must reach /login and /register.
        client.get("/set_language/zh-HK", follow_redirects=False)
        assert client.get("/me").json()["lang"] == "zh-HK"

        register_and_login(client)
        me = client.get("/me").json()
        assert me["authenticated"] is True
        assert me["lang"] == "zh-HK"


def test_translations_endpoint_serves_both_languages_with_matching_keys():
    with TestClient(app) as client:
        en = client.get("/translations/en").json()
        zh = client.get("/translations/zh-HK").json()
        assert en["app_name"] == "The Listening Tree"
        assert zh["app_name"] == "聆聽樹"
        assert set(en) == set(zh)


def test_config_exposes_google_flag_as_bool():
    with TestClient(app) as client:
        assert isinstance(client.get("/config").json()["google_enabled"], bool)
