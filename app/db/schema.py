"""Database schema setup — table/index DDL, run idempotently on startup.

No migration tool yet (see Alembic phase of the SDLC plan) — every
statement here is `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD
COLUMN IF NOT EXISTS`, safe to re-run on every process start.
"""
import asyncio
import builtins as _builtins
from typing import Optional

from app.db import queries as db


async def init_db() -> None:
    """Initialize PostgreSQL schema with all required tables and indexes."""
    conn = await db.get_db()
    c = conn.cursor()

    id_type = "BIGSERIAL PRIMARY KEY"
    id_ref = "BIGINT"

    # Users table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_type},
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    # `username` is in the CREATE TABLE above too, but that only takes effect
    # for a brand-new table — this database's `users` table predates the
    # column being added to the schema, so it needs the same explicit
    # ADD COLUMN treatment as the two below.
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0")
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP")
    # Google Sign-In: google_id links a row to a Google account; auth_provider
    # is informational only (password login still works for 'google' rows if
    # they ever set one). password stays NOT NULL — Google-only signups get a
    # random unusable hash instead (see /auth/google/callback).
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT")
    await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT NOT NULL DEFAULT 'password'")
    await c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users (google_id) WHERE google_id IS NOT NULL")

    # Reminders table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS reminders (
            id {id_type},
            user_id {id_ref} NOT NULL,
            label TEXT NOT NULL,
            reminder_time TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            repeat_type TEXT DEFAULT 'once',
            priority TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Chat history table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS chat_history (
            id {id_type},
            user_id {id_ref} NOT NULL,
            lang TEXT DEFAULT 'en',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_bot BOOLEAN NOT NULL,
            message TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT FALSE,
            token_count INTEGER
        )
    """)

    # Conversations table — groups chat_history rows into independent,
    # resumable threads (added after chat_history already had a flat log).
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS conversations (
            id {id_type},
            user_id {id_ref} NOT NULL,
            lang TEXT DEFAULT 'en',
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE
        )
    """)
    await c.execute("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS conversation_id BIGINT")
    await c.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE")
    await c.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tag TEXT")

    # One-time backfill: chat_history rows that predate the conversation_id
    # column get grouped into a single "legacy" conversation per (user_id,
    # lang) so existing history stays visible instead of being orphaned.
    # Guarded so it only does work the first time it finds orphaned rows.
    await c.execute("SELECT 1 FROM chat_history WHERE conversation_id IS NULL LIMIT 1")
    if c.fetchone():
        await c.execute("""
            INSERT INTO conversations (user_id, lang, title, created_at, updated_at)
            SELECT DISTINCT user_id, lang, NULL,
                   MIN(timestamp) OVER (PARTITION BY user_id, lang),
                   MAX(timestamp) OVER (PARTITION BY user_id, lang)
            FROM chat_history
            WHERE conversation_id IS NULL
        """)
        await c.execute("""
            UPDATE chat_history AS ch
            SET conversation_id = conv.id
            FROM conversations AS conv
            WHERE ch.conversation_id IS NULL
              AND conv.user_id = ch.user_id
              AND conv.lang = ch.lang
              AND conv.title IS NULL
        """)

    # Preferences table
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS preferences (
            id {id_type},
            user_id {id_ref} NOT NULL,
            pref_key TEXT NOT NULL,
            pref_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, pref_key)
        )
    """)

    # Email verification codes (registration)
    await c.execute(f"""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id {id_type},
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    await c.execute("CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users ((LOWER(email)))")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_email_verifications_email ON email_verifications ((LOWER(email)))")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, is_active)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_deleted ON chat_history(user_id, is_deleted)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_pref_user ON preferences(user_id, pref_key)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(user_id, created_at)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_lang ON chat_history(user_id, lang)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, lang, is_deleted)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id)")
    # Cover the columns cleanup_old_conversations/cleanup_old_chat_history
    # actually filter and order by — the plainer indexes above don't include
    # updated_at/timestamp, so those queries were scanning the full table.
    await c.execute("CREATE INDEX IF NOT EXISTS idx_conversations_cleanup ON conversations(user_id, lang, is_deleted, updated_at DESC)")
    await c.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation_cleanup ON chat_history(conversation_id, is_deleted, timestamp DESC)")

    # RLS: the app connects as the `postgres` role via asyncpg, which
    # bypasses RLS regardless, so this has no effect on app behavior — it
    # only matters for Supabase's PostgREST API (exposed by default on every
    # table in `public`). `conversations` was added after the other tables
    # already had this enabled and got missed; no policies needed since
    # PostgREST access isn't used by this app (fail-closed is correct here).
    await c.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")

    await conn.commit()
    await conn.close()
    print("[DB] ✅ PostgreSQL database initialized")


_db_initialized = False
_db_init_error: Optional[str] = None
_db_init_lock = asyncio.Lock()


async def ensure_db_initialized(strict: bool = False) -> bool:
    """Initialize DB schema once and cache the result for health checks."""
    global _db_initialized, _db_init_error
    if _db_initialized:
        return True

    async with _db_init_lock:
        if _db_initialized:
            return True
        try:
            await init_db()
            _db_initialized = True
            _db_init_error = None
            return True
        except Exception as e:
            _db_initialized = False
            _db_init_error = str(e)
            _builtins._original_print(f"[DB] ❌ Initialization failed: {e}")
            if strict:
                raise
            return False


def get_init_error() -> Optional[str]:
    return _db_init_error
