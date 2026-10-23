#!/usr/bin/env bash
# Many different users chatting with a slow *mock* model while others log in.
# No real AI, no quota, local e2e database only. USERS=50 by default.
set -euo pipefail
cd "$(dirname "$0")/../.."

API_PORT=${E2E_API_PORT:-5100}
USERS=${USERS:-50}
DB_URL="${E2E_DATABASE_URL:-postgresql://$(whoami)@127.0.0.1:5432/listening_tree_e2e?sslmode=disable}"
mkdir -p test-results

if curl -fs "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
  echo "Port $API_PORT already has a server on it; refusing to load-test something that may use another database." >&2
  exit 1
fi

${PYTHON:-python} tests/stress/mock_zhipu.py &
MOCK_PID=$!

SKIP_ENV_LOCAL=1 DATABASE_URL="$DB_URL" SUPABASE_POOLER_URL= POSTGRES_POOLER_URL= DATABASE_POOLER_URL= \
ZHIPU_API_KEY=mock ZHIPU_BASE_URL=http://127.0.0.1:5200 NEWS_API_KEY= HF_API_KEY= AZURE_COMMUNICATION_CONNECTION_STRING= GOOGLE_CLIENT_ID= GOOGLE_CLIENT_SECRET= \
TRUSTED_PROXY=1 LOG_LEVEL=WARNING SECRET_KEY=stress-secret PORT="$API_PORT" ${PYTHON:-python} run.py &
SERVER_PID=$!
trap 'kill $SERVER_PID $MOCK_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  curl -fs "http://127.0.0.1:$API_PORT/health" >/dev/null && break
  sleep 1
done
curl -fs "http://127.0.0.1:$API_PORT/health" >/dev/null || { echo "Backend did not start on port $API_PORT" >&2; exit 1; }

EMAILS=$(SKIP_ENV_LOCAL=1 DATABASE_URL="$DB_URL" SUPABASE_POOLER_URL= SECRET_KEY=stress-secret PYTHONPATH=. ${PYTHON:-python} tests/stress/seed_users.py "$USERS" 2>/dev/null | tail -1)
PASSWORD=$(PYTHONPATH=. ${PYTHON:-python} -c "from tests.integration.helpers import PASSWORD; print(PASSWORD)")

k6 run -e BASE_URL="http://127.0.0.1:$API_PORT" -e K6_USERS="$EMAILS" -e K6_PASSWORD="$PASSWORD" \
  --summary-export=test-results/stress-multiuser-summary.json tests/stress/k6-multiuser.js
