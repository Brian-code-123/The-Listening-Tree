"""Shared Jinja2 template environment and the cached static-file mount."""
import os

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


class CachedStaticFiles(StaticFiles):
    """Adds a Cache-Control header — static assets are otherwise served
    through this one Python function (Vercel's catch-all route sends
    everything here, not the edge network) with no caching hint at all.
    A modest max-age rather than a long/immutable one: nothing in this repo
    cache-busts asset URLs (no `?v=hash`), so style.css/speech.js could go
    stale for returning users after a deploy if cached too aggressively.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response
