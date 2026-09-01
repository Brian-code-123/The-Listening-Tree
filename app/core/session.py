"""Session helpers, template-context builder, and the remember-me cookie
middleware — used by nearly every router.
"""
import re
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from translations import get_all_translations

_CONTROL_CHAR_PATTERN = re.compile(r"[\r\n\t\x00-\x1f]")


def get_user(request: Request) -> int | None:
    """Return the logged-in user's DB id, or *None* if unauthenticated."""
    return request.session.get("user_id")


def get_lang(request: Request) -> str:
    """Return the current UI language code ('en' or 'zh-HK')."""
    return request.session.get("language", "en")


def require_login(request: Request) -> int:
    """Return user id or redirect to /login via 303 See Other."""
    uid = get_user(request)
    if uid is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return uid


def tpl_context(request: Request, **kwargs) -> dict:
    """Build a Jinja2 template context with common variables.

    Every template receives *request*, *lang*, and *translations* automatically.
    Extra keyword arguments are merged in.
    """
    lang = get_lang(request)
    ctx = {
        "request": request,
        "lang": lang,
        "translations": get_all_translations(lang),
    }
    ctx.update(kwargs)
    return ctx


_SAFE_REDIRECT_PATHS = {
    "/", "/chat", "/accessibility", "/hk_guide", "/login", "/register", "/profile",
}


def safe_redirect_target(request: Request) -> str:
    """Resolve where to send the user back to after switching language.

    Uses the Referer header so the language switch keeps the user on the
    page they were viewing (e.g. hk_guide, accessibility) instead of always
    bouncing to /. Only same-origin, known app paths are honored to avoid
    open-redirect via a spoofed Referer header.
    """
    referer = request.headers.get("referer")
    if not referer:
        return "/"
    try:
        parsed = urlsplit(referer)
        if parsed.netloc and parsed.netloc != request.url.netloc:
            return "/"
        if parsed.path in _SAFE_REDIRECT_PATHS:
            return parsed.path
    except ValueError:
        pass
    return "/"


class RememberMeCookieMiddleware:
    """Rewrites the session cookie to a browser-session cookie when the user
    did not opt into "remember me" at login — SessionMiddleware only supports
    a single fixed max_age, so this strips Max-Age/Expires from its Set-Cookie
    header after the fact when `session['remember_me']` is falsy.
    """

    _ATTR_PATTERN = re.compile(rb";\s*(?:Max-Age|Expires)=[^;]*", re.IGNORECASE)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            # Only strip when the user explicitly opted out. A missing key (an
            # older session, or the register flow) keeps the persistent cookie.
            if message["type"] == "http.response.start" and scope.get("session", {}).get("remember_me") is False:
                new_headers = []
                for name, value in message.get("headers", []):
                    if name.lower() == b"set-cookie" and value.startswith(b"lt_session="):
                        value = self._ATTR_PATTERN.sub(b"", value)
                    new_headers.append((name, value))
                message = {**message, "headers": new_headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
