"""add rate_limit_events table

Backing store for DB-based rate limiting (see app/services/rate_limit.py).
Not `slowapi`'s default in-memory storage — this app's production runtime
is Vercel serverless (api/index.py), where separate function instances have
independent memory, so an in-process counter wouldn't actually enforce a
shared limit. Postgres is already this app's real shared state, so it's the
counter store too, same idea as the existing `failed_login_attempts`/
`locked_until` account-lockout columns on `users`.

`(key, window_start)` is the natural primary key: `key` identifies what's
being limited (e.g. "login:203.0.113.4"), `window_start` is the fixed-size
time bucket the request landed in. Incrementing is a single atomic
`INSERT ... ON CONFLICT (key, window_start) DO UPDATE SET count = count + 1
RETURNING count` — no read-then-write race between concurrent requests
landing on different serverless instances.

Revision ID: 5d085fa573fe
Revises: 976eb0517898
Create Date: 2026-09-01 23:XX
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5d085fa573fe'
down_revision: Union[str, None] = '976eb0517898'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            key TEXT NOT NULL,
            window_start TIMESTAMPTZ NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (key, window_start)
        )
    """)
    # Cleanup (app/background.py's periodic loop) filters and deletes by
    # window_start alone — the primary key's leading column is `key`, which
    # doesn't help that query, so it needs its own index.
    op.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_window ON rate_limit_events(window_start)")
    # Same fail-closed pattern as every other public-schema table — the app
    # connects as the `postgres` role (bypasses RLS), this only matters for
    # Supabase's PostgREST API, which this app doesn't use.
    op.execute("ALTER TABLE rate_limit_events ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rate_limit_events")
