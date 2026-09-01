"""Top-level pages: home, accessibility mode, language switch."""
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core import config
from app.core.session import get_lang, get_user, safe_redirect_target, tpl_context
from app.core.templates import templates
from app.db import queries as db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    uid = get_user(request)
    if uid is None:
        return templates.TemplateResponse("login.html", tpl_context(request, google_enabled=config.GOOGLE_LOGIN_ENABLED))
    return templates.TemplateResponse("chat.html", tpl_context(request))


@router.get("/set_language/{lang}")
async def set_language(request: Request, lang: str):
    """Set user language preference, persist to database, and redirect back
    to the page the user was viewing (so switching language shows that same
    page, translated) instead of always bouncing to /chat."""
    if lang in ('en', 'zh-HK'):
        request.session['language'] = lang
        uid = get_user(request)
        if uid:
            conn = await db.get_db()
            c = conn.cursor()
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await db.db_insert_or_replace_preference(c, uid, 'language', lang, ts)
            await conn.commit()
            await conn.close()
    return RedirectResponse(url=safe_redirect_target(request), status_code=303)


@router.get("/accessibility", response_class=HTMLResponse)
async def accessibility_mode(request: Request):
    uid = get_user(request)
    if uid is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("accessibility.html", tpl_context(request))
