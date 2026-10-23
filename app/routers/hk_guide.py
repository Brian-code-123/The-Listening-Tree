"""HK public holidays, local news, and the HK Local Guide page/data."""
import time as _time
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.session import get_lang, get_user, tpl_context
from app.services.rate_limit import check_and_increment, client_key
from app.core.templates import templates
from app.services.hk_guide_data import (
    HK_HOLIDAYS,
    _hk_guide_cache,
    fetch_hk_news,
    get_hk_guide_data,
)

router = APIRouter()

# These three answer without signing in. A shared limit per address keeps them
# from being used to hammer the news provider's small quota or recompute data;
# it is generous enough for a care home sharing one connection.
PUBLIC_DATA_LIMIT = 120
PUBLIC_DATA_WINDOW_SECONDS = 60


async def _public_data_limited(request: Request):
    """A 429 response if this address has used up its public-data budget, else None."""
    if await check_and_increment(client_key(request, "public_data"), PUBLIC_DATA_LIMIT, PUBLIC_DATA_WINDOW_SECONDS):
        return None
    return JSONResponse({"error": "Too many requests. Please wait a moment."}, status_code=429)


@router.get("/get_hk_holidays")
async def get_hk_holidays(request: Request):
    """Return HK public holidays for FullCalendar."""
    if (limited := await _public_data_limited(request)) is not None:
        return limited
    lang = get_lang(request)
    events = []
    for h in HK_HOLIDAYS:
        events.append({
            "title": h["name_zh"] if lang == "zh-HK" else h["name_en"],
            "start": h["date"],
            "allDay": True,
            "color": "#E07A5F",
            "textColor": "#FFFFFF",
            "classNames": ["holiday-event"],
        })
    return JSONResponse({"holidays": events})


@router.get("/get_news")
async def get_news(request: Request):
    """Return HK local news articles."""
    if (limited := await _public_data_limited(request)) is not None:
        return limited
    lang = get_lang(request)
    articles = await fetch_hk_news(lang)
    return JSONResponse({"articles": articles})


@router.get("/hk_guide", response_class=HTMLResponse)
async def hk_guide_page(request: Request):
    """Render the HK Local Guide page."""
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "hk_guide.html", tpl_context(request))


@router.get("/get_hk_guide")
async def get_hk_guide(request: Request, refresh: int = 0):
    """Return HK local guide data as JSON (cached 30 min). `refresh` only counts
    for a signed-in user; otherwise anyone could bust the cache on demand."""
    if (limited := await _public_data_limited(request)) is not None:
        return limited
    lang = get_lang(request)
    now = _time.time()
    refresh = refresh if get_user(request) is not None else 0

    # Use cache unless forced refresh
    if (not refresh
            and _hk_guide_cache["data"]
            and (now - _hk_guide_cache["timestamp"]) < 1800
            and _hk_guide_cache["lang"] == lang):
        return JSONResponse(_hk_guide_cache["data"])

    items = get_hk_guide_data(lang)
    ts_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    result = {
        "items": items,
        "last_updated": ts_str,
        "total": len(items),
    }
    _hk_guide_cache["data"] = result
    _hk_guide_cache["timestamp"] = now
    _hk_guide_cache["lang"] = lang
    return JSONResponse(result)
