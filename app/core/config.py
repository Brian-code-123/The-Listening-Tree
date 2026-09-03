"""Cross-cutting app configuration: env loading, secrets, production flags,
Google OAuth client, and the small set of tuning constants shared across
more than one router. Feature-specific config (Zhipu AI, Azure email,
Hugging Face STT, NewsAPI) lives next to the service that uses it instead.

This module is deliberately the first thing `app/main.py`'s import chain
touches (directly, and transitively via app.background) — logging is
configured here so every other module's `logging.getLogger(__name__)`
call picks up the same level/format from the moment it's created.
"""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

try:
    from authlib.integrations.starlette_client import OAuth
    from authlib.integrations.base_client.errors import OAuthError
except ImportError:
    OAuth = None
    class OAuthError(Exception):
        pass

# Load environment variables from .env file. Path is repo root — this file
# lives at app/core/config.py, so parents[2] is the project root.
env_path = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(env_path, override=False)
env_local_path = Path(__file__).resolve().parents[2] / '.env.local'
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)

# ---------------------------------------------------------------------------
# Logging
# LOG_LEVEL controls verbosity (default INFO); set LOG_LEVEL=WARNING in
# production to get the old "quiet by default" behavior without a
# print-suppression hack.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Detect Vercel environment (serverless — no persistent filesystem)
ON_VERCEL = bool(os.environ.get("VERCEL"))

# Production environment detection
IN_PRODUCTION = ON_VERCEL or os.environ.get("ENVIRONMENT") == "production"

# Session secret: prefer explicit environment variable for production stability.
# If not provided, fall back to a generated ephemeral key (NOT recommended).
SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("SESSION_SECRET") or os.environ.get("FASTAPI_SECRET") or secrets.token_hex(16)
if IN_PRODUCTION and not (os.environ.get("SECRET_KEY") or os.environ.get("SESSION_SECRET") or os.environ.get("FASTAPI_SECRET")):
    raise RuntimeError("SECRET_KEY (or SESSION_SECRET/FASTAPI_SECRET) is required in production to prevent session loss across restarts.")
if SECRET_KEY and len(SECRET_KEY) >= 16:
    logger.info("[SECURITY] SECRET_KEY is set")
else:
    logger.warning("[SECURITY] No SECRET_KEY/SESSION_SECRET/FASTAPI_SECRET set — using ephemeral key")

REMEMBER_ME_MAX_AGE = 60 * 60 * 24 * 90

# ---------------------------------------------------------------------------
# Google Sign-In (OAuth 2.0 / OpenID Connect via Authlib)
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")
# Feature is entirely optional: absent client id/secret just hides the button.
GOOGLE_LOGIN_ENABLED = bool(OAuth and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
if IN_PRODUCTION and (GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET) and not GOOGLE_LOGIN_ENABLED:
    raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must both be set to enable Google sign-in.")

oauth = OAuth() if OAuth else None
if GOOGLE_LOGIN_ENABLED:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# ---------------------------------------------------------------------------
# In-memory state  (lost on server restart — by design)
# ---------------------------------------------------------------------------
# Per-user quiz progress: { user_id: { is_game_mode, current_index, ... } }
user_game_states: dict = {}

# Keep only the most recent chat messages per user/language.
# Older rows are soft-deleted to bound table growth while preserving continuity.
CHAT_HISTORY_MAX_MESSAGES_PER_LANG = int(os.environ.get("CHAT_HISTORY_MAX_MESSAGES_PER_LANG", "200"))
# Per-conversation cap on top of the per-conversation message cap above —
# without this, a user with hundreds of conversations would keep them all
# forever. Oldest conversations (by updated_at) beyond this count are
# soft-deleted wholesale rather than having their messages pruned piecemeal.
CONVERSATION_MAX_PER_LANG = int(os.environ.get("CONVERSATION_MAX_PER_LANG", "50"))

# Fixed, small set of everyday-life labels a conversation can be tagged
# with — deliberately not free-text (elderly-friendly: pick from a short
# list, don't type a category name). Icon/color drive the chip UI on the
# conversation history page; the label text itself lives in translations.py
# as `tag_<key>` (EN + zh-HK).
CONVERSATION_TAGS = {
    "family": {"icon": "fa-people-roof", "color": "#5B8DEF"},
    "friends": {"icon": "fa-user-friends", "color": "#F2CC8F"},
    "health": {"icon": "fa-heart-pulse", "color": "#5B9A7D"},
    "daily": {"icon": "fa-sun", "color": "#98A2B3"},
    "important": {"icon": "fa-star", "color": "#E07A5F"},
}
