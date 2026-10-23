"""security hardening: session versions, security events, consent, unique email

Additive only, so the new code can be deployed after this runs and the old
code keeps working against the new schema.

- users.session_version: bumped on logout / password change; a session cookie
  carries the version it was issued under (missing = 0), so older cookies are
  rejected without a server-side session store.
- users.consent_at / consent_version: when and to which privacy-notice version
  the user agreed at registration.
- security_events: audit trail (login failures, lockouts, password changes...).
  RLS on, no policies: same fail-closed pattern as every other public table.
- A unique index on LOWER(email): the app already lowercases, but nothing in
  the database stopped a second row that differed only by case.

Revision ID: a3c91e7d2b54
Revises: 5d085fa573fe
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3c91e7d2b54'
down_revision: Union[str, None] = '5d085fa573fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_at TIMESTAMP")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_version TEXT")
    op.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id BIGSERIAL PRIMARY KEY,
            ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            event TEXT NOT NULL,
            user_id BIGINT,
            email_hash TEXT,
            ip TEXT,
            ua TEXT,
            detail JSONB
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_security_events_ts ON security_events(ts)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_security_events_user ON security_events(user_id)")
    op.execute("ALTER TABLE security_events ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower_unique ON users ((LOWER(email)))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_email_lower_unique")
    op.execute("DROP TABLE IF EXISTS security_events")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS consent_version")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS consent_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS session_version")
