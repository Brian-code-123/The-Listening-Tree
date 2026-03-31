#!/usr/bin/env bash
set -euo pipefail

# Recover local Supabase DB by ensuring Docker daemon is ready,
# then starting DB-only service and running a smoke query.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/4] Ensuring Docker daemon is running..."
open -a Docker >/dev/null 2>&1 || true

# Prefer Docker Desktop context because Supabase CLI expects this socket path on macOS.
docker context use desktop-linux >/dev/null 2>&1 || true

for i in {1..40}; do
  # Docker can report a context before daemon/socket is fully ready, so validate both.
  if [[ -S "/Users/lochunman/.docker/run/docker.sock" ]] && docker info >/dev/null 2>&1; then
    echo "Docker is ready."
    break
  fi
  if [[ "$i" -eq 40 ]]; then
    echo "ERROR: Docker daemon/socket is not ready after waiting."
    echo "Current Docker contexts:"
    docker context ls || true
    exit 1
  fi
  sleep 3
done

echo "[2/4] Starting Supabase Postgres (db-only)..."
supabase db start --debug

echo "[3/4] Verifying DB container health..."
for i in {1..30}; do
  if docker ps --format '{{.Names}} {{.Status}}' | grep -q '^supabase_db_.*(healthy)$'; then
    echo "Supabase DB container is healthy."
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Supabase DB container did not become healthy in time."
    docker ps --format 'table {{.Names}}\t{{.Status}}' | grep supabase_db_ || true
    exit 1
  fi
  sleep 2
done

echo "[4/4] Running DB smoke query..."
CONTAINER_NAME="$(docker ps --format '{{.Names}}' | grep '^supabase_db_' | head -n 1)"
docker exec "$CONTAINER_NAME" psql -U postgres -d postgres -c 'select now() as db_time, current_database() as db;'

echo "Supabase local DB recovery complete."
