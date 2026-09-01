"""enable RLS on alembic_version

Alembic creates alembic_version itself as bookkeeping — it wasn't in
app/db/schema.py and isn't application data, but it's still a table in the
`public` schema, which Supabase's PostgREST API exposes by default. Every
other table in this schema has RLS enabled fail-closed (no policies, so the
anon/authenticated PostgREST roles get nothing); alembic_version was the one
gap, flagged as an ERROR-level finding by Supabase's advisor the moment this
table appeared. This closes it the same way the rest already are.

Revision ID: 976eb0517898
Revises: 4b1eb8a60471
Create Date: 2026-09-01 22:59:25.251470

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '976eb0517898'
down_revision: Union[str, None] = '4b1eb8a60471'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
