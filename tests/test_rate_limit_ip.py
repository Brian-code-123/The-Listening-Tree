import asyncio

import pytest
from starlette.requests import Request

from app.services import rate_limit


def _request(xff: str | None = None, host: str | None = "9.9.9.9") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({
        "type": "http", "method": "GET", "path": "/", "headers": headers, "query_string": b"",
        "server": ("app.example.com", 443), "scheme": "https",
        "client": (host, 1234) if host else None,
    })


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY", raising=False)


def test_forwarded_for_is_trusted_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert rate_limit.client_ip(_request("203.0.113.5, 10.0.0.1")) == "203.0.113.5"


def test_forwarded_for_is_ignored_without_a_trusted_proxy():
    assert rate_limit.client_ip(_request("203.0.113.5")) == "9.9.9.9"


def test_forwarded_for_is_used_when_a_proxy_is_declared_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY", "1")
    assert rate_limit.client_ip(_request("203.0.113.5")) == "203.0.113.5"


@pytest.mark.parametrize("bad", ["not-an-ip", "", "1" * 200, "999.1.1.1", "203.0.113.5; DROP TABLE x"])
def test_garbage_forwarded_for_falls_back_to_the_socket_address(monkeypatch, bad):
    monkeypatch.setenv("VERCEL", "1")
    assert rate_limit.client_ip(_request(bad)) == "9.9.9.9"


def test_missing_client_is_unknown():
    assert rate_limit.client_ip(_request(host=None)) == "unknown"


def test_ipv6_addresses_in_one_64_share_a_bucket(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    a = rate_limit.client_ip(_request("2001:db8:1:2::1"))
    b = rate_limit.client_ip(_request("2001:db8:1:2:ffff::9"))
    c = rate_limit.client_ip(_request("2001:db8:1:3::1"))
    assert a == b
    assert a != c


def test_client_key_joins_bucket_and_ip():
    assert rate_limit.client_key(_request(), "login") == "login:9.9.9.9"


def test_database_failure_raises_rate_limit_unavailable(monkeypatch):
    async def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(rate_limit.db, "get_db", _boom)
    with pytest.raises(rate_limit.RateLimitUnavailable):
        asyncio.run(rate_limit.check_and_increment("login:1.2.3.4", 10, 60))


def test_reset_key_deletes_every_window_of_the_key(monkeypatch):
    calls = []

    class _Cursor:
        async def execute(self, sql, params=()):
            calls.append((" ".join(sql.split()), params))

    class _Conn:
        def cursor(self):
            return _Cursor()

        async def commit(self):
            calls.append(("commit", ()))

        async def close(self):
            calls.append(("close", ()))

    async def _get_db():
        return _Conn()

    monkeypatch.setattr(rate_limit.db, "get_db", _get_db)
    asyncio.run(rate_limit.reset_key("login_fail:a@b.c:1.2.3.4"))
    assert calls[0] == ("DELETE FROM rate_limit_events WHERE key = ?", ("login_fail:a@b.c:1.2.3.4",))
    assert ("commit", ()) in calls and ("close", ()) in calls


def test_limiter_outage_answers_503_not_a_stack_trace(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.routers import auth as auth_router

    async def _down(*_args, **_kwargs):
        raise rate_limit.RateLimitUnavailable()

    monkeypatch.setattr(auth_router, "check_and_increment", _down)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/auth/login",
            data={"email": "a@example.com", "password": "whatever123"},
            headers={"accept": "application/json"},
        )
    assert resp.status_code == 503
    assert resp.json()["success"] is False
    assert "Traceback" not in resp.text
