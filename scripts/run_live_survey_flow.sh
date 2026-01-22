#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
BASE_URL="http://${HOST}:${PORT}"

SURVEY_URL="${SURVEY_URL:-https://example.com/survey}"
CONTINUE_SELECTOR="${CONTINUE_SELECTOR:-button:has-text(\"Continue\")}"
FINISH_SELECTOR="${FINISH_SELECTOR:-button:has-text(\"Finish\")}"

post_msg() {
  local msg="$1"
  local payload
  payload=$(MSG="${msg}" python3 - <<'PY'
import json
import os
print(json.dumps({"message": os.environ["MSG"]}))
PY
)
  curl -sS "${BASE_URL}/chat" \
    -H "content-type: application/json" \
    -d "${payload}"
}

if ! curl -sS "${BASE_URL}/health" >/dev/null; then
  echo "Agent service not running at ${BASE_URL}."
  echo "Start it with: ./scripts/debug_daemon.sh start"
  exit 1
fi

echo "Starting multi-step survey fill"
post_msg "Fill the survey at ${SURVEY_URL} using stored personal info. Use survey.fill_multi_step with continue_selector '${CONTINUE_SELECTOR}' and finish_selectors ['${FINISH_SELECTOR}']. Use session_id 'survey-live'. If missing data, ask me."
echo ""

echo "Done. Inspect log_dump.txt or /ui for details."
