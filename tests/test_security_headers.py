import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import security_headers as sh
from run import app

ROOT = Path(__file__).resolve().parents[1]


def _in_production(code: str, **env) -> dict:
    """Run `code` in a fresh interpreter that believes it is on Vercel, and
    return the JSON it prints (module-level switches are read at import)."""
    full_env = {
        **os.environ, "VERCEL": "1", "SECRET_KEY": "x" * 32, "SKIP_ENV_LOCAL": "1",
        "DATABASE_URL": "postgresql://u@127.0.0.1:5432/none?sslmode=disable", "PYTHONPATH": str(ROOT), **env,
    }
    out = subprocess.run([sys.executable, "-c", code], env=full_env, capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout.strip().splitlines()[-1])


_PROBE = """
import json
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
h = c.get('/health')
pre = c.options('/me', headers={'Origin': ORIGIN, 'Access-Control-Request-Method': 'GET'})
print(json.dumps({
  'docs': c.get('/docs').status_code, 'redoc': c.get('/redoc').status_code, 'openapi': c.get('/openapi.json').status_code,
  'csp': {k: v for k, v in h.headers.items() if k.startswith('content-security-policy')},
  'cors': pre.headers.get('access-control-allow-origin'),
}))
"""


def _probe(origin="http://localhost:3001", **env):
    return _in_production(_PROBE.replace("ORIGIN", repr(origin)), **env)


@pytest.mark.parametrize("path", ["/health", "/me", "/no-such-route"])
def test_every_kind_of_response_carries_the_security_headers(path):
    resp = TestClient(app).get(path)
    for name, value in sh.SECURITY_HEADERS.items():
        assert resp.headers.get(name) == value, name


def test_no_csp_outside_production():
    resp = TestClient(app).get("/health")
    assert not any(k.startswith("content-security-policy") for k in resp.headers)


def test_csp_starts_as_report_only_and_is_enforced_on_request():
    assert list(_probe()["csp"]) == ["content-security-policy-report-only"]
    enforced = _probe(CSP_ENFORCE="1")["csp"]
    assert list(enforced) == ["content-security-policy"]
    assert enforced["content-security-policy"] == sh.CSP_VALUE


def test_csp_blocks_third_party_scripts_framing_and_plugins():
    directives = dict(d.strip().split(" ", 1) for d in sh.CSP_VALUE.split(";") if d.strip())
    assert directives["default-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"
    assert directives["object-src"] == "'none'"
    assert directives["script-src"] == "'self' 'unsafe-inline'"
    assert "https:" not in sh.CSP_VALUE and "*" not in sh.CSP_VALUE
    assert sh.SECURITY_HEADERS["Permissions-Policy"].startswith("microphone=(self)")


def test_api_docs_exist_locally_but_not_in_production():
    local = TestClient(app)
    assert local.get("/openapi.json").status_code == 200
    prod = _probe()
    assert (prod["docs"], prod["redoc"], prod["openapi"]) == (404, 404, 404)


def test_dev_origins_are_allowed_locally_but_never_in_production():
    assert "http://localhost:3001" in sh.cors_origins(in_production=False)
    prod = sh.cors_origins(in_production=True)
    assert prod == ["https://the-listening-tree.vercel.app", "capacitor://localhost"]
    assert _probe("http://localhost:3001")["cors"] is None
    assert _probe("capacitor://localhost")["cors"] == "capacitor://localhost"


def test_health_db_reveals_nothing_about_the_infrastructure(monkeypatch):
    from tests.integration.helpers import PASSWORD  # noqa: F401  (only to share the signed-in flow below)

    client = TestClient(app)
    anonymous = client.get("/health/db").json()
    assert anonymous == {"ok": True}
    client.post("/register", data={"email": "h@example.com", "password": "TestPass123!", "confirm_password": "TestPass123!", "verification_code": "123456"}, follow_redirects=False)
    assert client.get("/health/db").json() == {"ok": True}


def test_an_unhandled_error_does_not_leak_its_message():
    async def boom():
        raise RuntimeError("secret detail for victim@example.com")

    app.add_api_route("/_test_boom", boom)
    try:
        resp = TestClient(app, raise_server_exceptions=False).get("/_test_boom")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/_test_boom"]
    assert resp.status_code == 500
    assert "victim@example.com" not in resp.text and "RuntimeError" not in resp.text
    assert resp.json()["detail"] == "Internal error" and resp.json()["request_id"]


def test_the_next_config_sends_the_same_headers():
    # Adjacent string literals joined with "+" across lines count as one value.
    text = re.sub(r'"\s*\+\s*\n\s*"', "", (ROOT / "web-next" / "next.config.ts").read_text())
    for name, value in sh.SECURITY_HEADERS.items():
        assert name in text and value in text, name
    assert sh.CSP_VALUE in text
    assert "Content-Security-Policy-Report-Only" in text and "CSP_ENFORCE" in text
