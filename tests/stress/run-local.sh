#!/usr/bin/env bash
# Runs the k6 load test against a hermetic local backend (own e2e DB, no LLM,
# no email, never .env.local). PROFILE=smoke for a 25s run.
set -euo pipefail
cd "$(dirname "$0")/../.."

API_PORT=${E2E_API_PORT:-5100}
DB_URL="${E2E_DATABASE_URL:-postgresql://$(whoami)@127.0.0.1:5432/listening_tree_e2e?sslmode=disable}"
mkdir -p test-results

SKIP_ENV_LOCAL=1 DATABASE_URL="$DB_URL" SUPABASE_POOLER_URL= POSTGRES_POOLER_URL= DATABASE_POOLER_URL= \
ZHIPU_API_KEY= NEWS_API_KEY= HF_API_KEY= AZURE_COMMUNICATION_CONNECTION_STRING= GOOGLE_CLIENT_ID= GOOGLE_CLIENT_SECRET= \
LOG_LEVEL=WARNING SECRET_KEY=stress-secret PORT="$API_PORT" ${PYTHON:-python} run.py &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  curl -fs "http://127.0.0.1:$API_PORT/health" >/dev/null && break
  sleep 1
done

export E2E_DATABASE_URL="$DB_URL" STRESS_BASE_URL="http://127.0.0.1:$API_PORT"
CREDS=$(npx tsx tests/stress/seed-user.ts)
K6_EMAIL=$(echo "$CREDS" | python3 -c 'import sys,json;print(json.load(sys.stdin)["email"])')
K6_PASSWORD=$(echo "$CREDS" | python3 -c 'import sys,json;print(json.load(sys.stdin)["password"])')

k6 run -e BASE_URL="$STRESS_BASE_URL" -e K6_EMAIL="$K6_EMAIL" -e K6_PASSWORD="$K6_PASSWORD" \
  -e PROFILE="${PROFILE:-full}" --summary-export=test-results/stress-summary.json tests/stress/k6-load.js
