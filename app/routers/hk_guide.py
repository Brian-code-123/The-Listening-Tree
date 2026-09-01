"""HK public holidays, local news, and the HK Local Guide page/data."""
import time as _time
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.session import get_lang, get_user, tpl_context
from app.core.templates import templates
from app.services.hk_guide_data import (
    HK_HOLIDAYS,
    _hk_guide_cache,
    fetch_hk_news,
    get_hk_guide_data,
)

router = APIRouter()


@router.get("/get_hk_holidays")
async def get_hk_holidays(request: Request):
    """Return HK public holidays for FullCalendar."""
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
    lang = get_lang(request)
    articles = await fetch_hk_news(lang)
    return JSONResponse({"articles": articles})


@router.get("/hk_guide", response_class=HTMLResponse)
async def hk_guide_page(request: Request):
    """Render the HK Local Guide page."""
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("hk_guide.html", tpl_context(request))


@router.get("/get_hk_guide")
async def get_hk_guide(request: Request, refresh: int = 0):
    """Return HK local guide data as JSON (cached 30 min)."""
    lang = get_lang(request)
    now = _time.time()

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
