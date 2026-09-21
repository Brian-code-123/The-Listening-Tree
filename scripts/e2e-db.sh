#!/usr/bin/env bash
# Creates the local hermetic e2e database and migrates it. Never touches
# .env.local (SKIP_ENV_LOCAL=1) so it can't be redirected at production.
set -euo pipefail
DB=listening_tree_e2e
createdb "$DB" 2>/dev/null || true
export SKIP_ENV_LOCAL=1
export DATABASE_URL="postgresql://$(whoami)@127.0.0.1:5432/$DB?sslmode=disable"
export SUPABASE_POOLER_URL="" POSTGRES_POOLER_URL="" DATABASE_POOLER_URL=""
alembic upgrade head
echo "e2e DB ready: $DB"
