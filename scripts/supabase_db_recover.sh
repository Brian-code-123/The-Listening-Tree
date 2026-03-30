#!/usr/bin/env bash
set -euo pipefail

# Recover local Supabase DB by ensuring Docker daemon is ready,
# then starting DB-only service and running a smoke query.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/4] Ensuring Docker daemon is running..."
open -a Docker >/dev/null 2>&1 || true

for i in {1..30}; do
  if docker info >/dev/null 2>&1; then
    echo "Docker is ready."
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Docker daemon is not ready after waiting."
    exit 1
  fi
  sleep 3
done

echo "[2/4] Starting Supabase Postgres (db-only)..."
supabase db start --debug

echo "[3/4] Verifying DB container health..."
if ! docker ps --format '{{.Names}} {{.Status}}' | grep -q '^supabase_db_.*(healthy)$'; then
  echo "ERROR: Supabase DB container is not healthy."
  docker ps --format 'table {{.Names}}\t{{.Status}}' | grep supabase_db_ || true
  exit 1
fi

echo "[4/4] Running DB smoke query..."
CONTAINER_NAME="$(docker ps --format '{{.Names}}' | grep '^supabase_db_' | head -n 1)"
docker exec "$CONTAINER_NAME" psql -U postgres -d postgres -c 'select now() as db_time, current_database() as db;'

echo "Supabase local DB recovery complete."
