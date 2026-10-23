"""Cap how much request body the app will read.

The multipart and form parsers read a whole body before any route code runs, so
a size check inside a route comes too late to stop a huge upload from being
buffered. This turns oversized requests away first, by the declared
Content-Length and, for chunked bodies that declare nothing, by counting bytes
as they arrive. Vercel also caps bodies, but this keeps the limit under our
control and holds on any other host.
"""
import json

# Ordinary requests are small forms and JSON; 1 MB is far above any of them.
DEFAULT_MAX_BODY_BYTES = 1_000_000
# A 10 MB voice clip plus its multipart framing.
UPLOAD_MAX_BODY_BYTES = 11 * 1024 * 1024
UPLOAD_PATHS = ("/transcribe",)
_BODY_METHODS = {"POST", "PUT", "PATCH"}


class _TooLarge(Exception):
    pass


async def _reply(send, status: int, message: str) -> None:
    body = json.dumps({"detail": message, "error": message, "text": ""}).encode()
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
    ]})
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return

        limit = UPLOAD_MAX_BODY_BYTES if scope["path"] in UPLOAD_PATHS else DEFAULT_MAX_BODY_BYTES
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                await _reply(send, 400, "Invalid Content-Length header")
                return
            if size < 0:
                await _reply(send, 400, "Invalid Content-Length header")
                return
            if size > limit:
                await _reply(send, 413, "Request body too large")
                return

        received = 0
        too_large = False

        async def counting_receive():
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
                    raise _TooLarge()
            return message

        started = False

        async def tracking_send(message):
            # FastAPI turns any error raised while reading the body into its own
            # 400, so once the cap tripped, swap whatever the app answers for 413.
            nonlocal started
            if too_large:
                if not started:
                    started = True
                    await _reply(send, 413, "Request body too large")
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await _reply(send, 413, "Request body too large")
