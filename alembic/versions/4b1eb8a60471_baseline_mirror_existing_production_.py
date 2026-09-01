"""baseline: mirror existing production schema

This migration is a straight port of app/db/schema.py's DDL as of the day
Alembic was introduced — it exists so a *fresh* database (a new contributor,
a CI ephemeral Postgres, a disaster-recovery restore) can be brought up to
the same schema Alembic now tracks going forward. It is NOT meant to ever
run against the existing production Supabase database — that DB already has
this schema, so production is onboarded via `alembic stamp head` instead of
`alembic upgrade head` (recording "already at this revision" without
re-running the DDL). See docs/REQUIREMENTS.md / the SDLC plan for why.

Revision ID: 4b1eb8a60471
Revises:
Create Date: 2026-09-01 22:57:45.179982

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4b1eb8a60471'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT NOT NULL DEFAULT 'password'")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users (google_id) WHERE google_id IS NOT NULL")

    op.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            label TEXT NOT NULL,
            reminder_time TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            repeat_type TEXT DEFAULT 'once',
            priority TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            lang TEXT DEFAULT 'en',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_bot BOOLEAN NOT NULL,
            message TEXT NOT NULL,
            is_deleted BOOLEAN DEFAULT FALSE,
            token_count INTEGER
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            lang TEXT DEFAULT 'en',
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE
        )
    """)
    op.execute("ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS conversation_id BIGINT")
    op.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tag TEXT")

    op.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            pref_key TEXT NOT NULL,
            pref_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, pref_key)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id BIGSERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users ((LOWER(email)))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_email_verifications_email ON email_verifications ((LOWER(email)))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_deleted ON chat_history(user_id, is_deleted)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pref_user ON preferences(user_id, pref_key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_lang ON chat_history(user_id, lang)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, lang, is_deleted)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_history(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_cleanup ON conversations(user_id, lang, is_deleted, updated_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation_cleanup ON chat_history(conversation_id, is_deleted, timestamp DESC)")

    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Deliberately not implemented: this is the baseline revision — "downgrading"
    # past it means dropping every table in the live application's schema.
    # If that's ever genuinely intended, do it by hand with eyes open, not via
    # `alembic downgrade`, which makes destroying all data one flag away.
    raise NotImplementedError(
        "Refusing to auto-downgrade past the baseline revision — this would "
        "drop every application table. Do this by hand if truly intended."
    )
