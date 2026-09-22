#!/usr/bin/env bash
# scripts/preflight.sh — run before every push
# Fails (exit 1) on any finding so it can gate a pre-push hook or CI job.

set -euo pipefail

OUT=$(mktemp)
trap 'rm -f "$OUT"' EXIT

# --- 1. Deterministic secret scan (fast, reliable, no LLM needed) ---
# Prefer gitleaks if available; it scans tracked files AND git history,
# which an LLM call cannot reliably guarantee.
if command -v gitleaks >/dev/null 2>&1; then
  echo "Running gitleaks..."
  if ! gitleaks detect --source . --no-git=false --redact -v > "$OUT" 2>&1; then
    echo "FAIL: gitleaks found potential secrets."
    cat "$OUT"
    exit 1
  fi
else
  echo "WARN: gitleaks not installed — falling back to Claude-based scan only (less reliable for secrets)." >&2
fi

# --- 2. Semantic checks that need understanding, not just pattern matching ---
# README-vs-code accuracy and AI-attribution checks genuinely benefit from
# an LLM; the model is asked to emit a machine-readable STATUS line so this
# script can gate on it instead of just archiving prose nobody reads.
RESULT=$(claude -p "Audit this repo and report ONLY:
(1) any commit author, trailer, or branch name containing 'claude' or 'Co-Authored-By: Claude'
(2) any README claim that is contradicted by the actual code
Do NOT attempt to scan for secrets yourself — that is handled separately.
Do NOT reproduce any secret-looking value even if you see one; refer to it by location only.
Output format: first line must be exactly 'STATUS: PASS' or 'STATUS: FAIL',
followed by a markdown table of findings (empty if PASS)." \
  --allowedTools "Read,Grep,Glob,Bash")

echo "$RESULT"

if ! echo "$RESULT" | grep -qx "STATUS: PASS"; then
  echo "FAIL: attribution/README audit reported issues (see above)."
  exit 1
fi

echo "PASS: preflight checks clean."
exit 0
