import os
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
import urllib.error

BASE_URL = os.getenv("VERCEL_E2E_BASE_URL", "https://the-listening-tree.vercel.app")


def run() -> int:
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    no_redirect_opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        _NoRedirect(),
    )
    results = []

    def open_with_retry(http_opener, request, timeout: int, retries: int = 3):
        last_exc = None
        for attempt in range(retries):
            try:
                return http_opener.open(request, timeout=timeout)
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                raise
        if last_exc:
            raise last_exc

    def check(name: str, ok: bool, detail: str) -> None:
        print(f"{'PASS' if ok else 'FAIL'} | {name} | {detail}")
        results.append(ok)

    # Health endpoints
    for path in ["/health", "/health/db"]:
        try:
            req = urllib.request.Request(BASE_URL + path, method="GET")
            with opener.open(req, timeout=30) as resp:
                body = resp.read(300).decode("utf-8", "ignore")
                check(path, resp.status == 200, f"status={resp.status}, body={body[:120]!r}")
        except urllib.error.HTTPError as exc:
            body = exc.read(300).decode("utf-8", "ignore")
            check(path, False, f"http_error={exc.code}, body={body[:120]!r}")
        except Exception as exc:
            check(path, False, f"error={exc}")

    # Register
    email = f"speckitty_{int(time.time())}@example.com"
    password = "StrongPass123"
    register_body = urllib.parse.urlencode(
        {
            "email": email,
            "password": password,
            "confirm_password": password,
        }
    ).encode("utf-8")

    try:
        req = urllib.request.Request(BASE_URL + "/register", data=register_body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with open_with_retry(no_redirect_opener, req, timeout=30, retries=1) as resp:
                location = resp.headers.get("Location", "")
                final_url = getattr(resp, "url", "")
                ok = (resp.status in (302, 303) and "/login" in location) or (
                    resp.status == 200 and "/login" in final_url
                )
                check("register", ok, f"status={resp.status}, location={location}, final_url={final_url}, email={email}")
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location", "")
            ok = exc.code in (302, 303) and "/login" in location
            check("register", ok, f"status={exc.code}, location={location}, email={email}")
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", "ignore")
        check("register", False, f"http_error={exc.code}, body={body[:120]!r}")
    except Exception as exc:
        check("register", False, f"error={exc}")

    # Login
    login_body = urllib.parse.urlencode(
        {
            "email": email,
            "password": password,
        }
    ).encode("utf-8")

    try:
        req = urllib.request.Request(BASE_URL + "/login", data=login_body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with open_with_retry(no_redirect_opener, req, timeout=30) as resp:
                location = resp.headers.get("Location", "")
                has_session = any(cookie.name == "lt_session" for cookie in cj)
                ok = resp.status in (302, 303) and location.startswith("/") and has_session
                check("login", ok, f"status={resp.status}, location={location}, session_cookie={has_session}")
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location", "")
            has_session = any(cookie.name == "lt_session" for cookie in cj)
            ok = exc.code in (302, 303) and location.startswith("/") and has_session
            check("login", ok, f"status={exc.code}, location={location}, session_cookie={has_session}")
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", "ignore")
        check("login", False, f"http_error={exc.code}, body={body[:120]!r}")
    except Exception as exc:
        has_session = any(cookie.name == "lt_session" for cookie in cj)
        check("login", has_session, f"error={exc}, session_cookie={has_session}")

    # Core function: chat response endpoint
    chat_body = urllib.parse.urlencode({"msg": "hello"}).encode("utf-8")
    try:
        req = urllib.request.Request(BASE_URL + "/get_response", data=chat_body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with open_with_retry(opener, req, timeout=45) as resp:
            text = resp.read().decode("utf-8", "ignore")
            ok = resp.status == 200 and len(text) > 0 and "Invalid or expired session" not in text
            check("get_response", ok, f"status={resp.status}, body_len={len(text)}")
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", "ignore")
        check("get_response", False, f"http_error={exc.code}, body={body[:120]!r}")
    except Exception as exc:
        check("get_response", False, f"error={exc}")

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
