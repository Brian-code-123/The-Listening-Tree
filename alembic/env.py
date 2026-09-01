import os
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# There are no SQLAlchemy ORM models in this codebase (the app talks to
# Postgres directly via asyncpg — see app/db/queries.py) — schema lives as
# hand-written DDL in app/db/schema.py. So there's no `target_metadata` for
# autogenerate to diff against; every migration in versions/ is hand-written
# `op.execute(...)` SQL, ported straight from schema.py. `alembic revision
# --autogenerate` will not produce anything meaningful here — use
# `alembic revision -m "..."` and write the op.execute() calls by hand.
target_metadata = None

# Migrations run as a one-off admin operation (local shell or a CI/deploy
# step), never inside the Vercel serverless request path — so this uses a
# plain synchronous psycopg2 connection instead of the app's runtime
# asyncpg pool. That's the deliberate choice here, not just "simpler":
# psycopg2 sidesteps asyncpg's documented SSL-negotiation hang against
# Supabase's pooler (see app/db/pool.py's ASYNCPG_DSN comment) since it's an
# entirely different driver/handshake path, and a single blocking
# connection is exactly the right tool for a rare, deliberate schema change.
#
# Prefer the SAME pooler URL app/db/pool.py uses at runtime, not
# DATABASE_URL's direct host — confirmed by hand that the direct host
# (db.<project>.supabase.co) is IPv6-only and does not resolve on this
# network (and likely won't on most CI runners either), while the pooler
# host is IPv4-reachable. DATABASE_URL is kept only as a last-resort
# fallback for environments where it happens to be the reachable one.
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path, override=False)
_env_local_path = Path(__file__).resolve().parents[1] / ".env.local"
if _env_local_path.exists():
    load_dotenv(_env_local_path, override=True)


def _resolve_migration_db_url() -> str:
    raw_url = (
        os.environ.get("SUPABASE_POOLER_URL")
        or os.environ.get("POSTGRES_POOLER_URL")
        or os.environ.get("DATABASE_POOLER_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not raw_url:
        raise RuntimeError(
            "SUPABASE_POOLER_URL (preferred) or DATABASE_URL is required to "
            "run migrations."
        )
    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    # SQLAlchemy needs an explicit dialect+driver; psycopg2 is the sync
    # driver installed for this purpose (see requirements.txt).
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


config.set_main_option("sqlalchemy.url", _resolve_migration_db_url())

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
