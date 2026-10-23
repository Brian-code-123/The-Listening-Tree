"""Browser security headers, and the CORS allowlist.

One definition, used twice: here for responses from the FastAPI service, and
mirrored in web-next/next.config.ts for the pages Next serves (a test keeps the
two identical). Vercel adds HSTS itself.

The Content-Security-Policy is sent only in production (local dev servers need
inline and eval tricks it would block) and starts as *Report-Only*, so a missed
source shows up as a console message instead of a broken page; set
CSP_ENFORCE=1 once a deployment is clean. `'unsafe-inline'` for scripts is a
deliberate trade-off: the pages are prerendered at build time, so there is no
per-request response to put a nonce in. The policy still blocks other origins'
scripts, eval, framing, plugins and foreign form targets.
"""
import os

from starlette.datastructures import MutableHeaders

from app.core import config

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    # The microphone is the one feature the app needs; everything else is off.
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=(), payment=()",
}

CSP_VALUE = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; media-src 'self' blob: data:; font-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'"
)


def csp_header_name() -> str:
    enforced = os.environ.get("CSP_ENFORCE") == "1"
    return "Content-Security-Policy" if enforced else "Content-Security-Policy-Report-Only"


def cors_origins(in_production: bool) -> list[str]:
    """Origins allowed to make credentialed cross-origin calls. The localhost
    entries are for developers and must not exist on the live site."""
    origins = ["https://the-listening-tree.vercel.app", "capacitor://localhost"]
    if not in_production:
        origins += ["http://localhost", "http://localhost:5000", "http://localhost:5001", "http://localhost:3001"]
    return origins


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers[name] = value
                if config.IN_PRODUCTION:
                    headers[csp_header_name()] = CSP_VALUE
            await send(message)

        await self.app(scope, receive, send_with_headers)
