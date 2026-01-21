#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
BASE_URL="http://${HOST}:${PORT}"

post_msg() {
  local msg="$1"
  local payload
  payload=$(MSG="${msg}" python - <<'PY'
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

echo "1) Remember credentials"
post_msg "Remember my login for example.com: username ada, password hunter2."
echo ""

echo "2) Store a login procedure with graph schema"
post_msg "Create a graph-based procedure (schema_version ksg-procedure-0.2). name 'Example Login', description 'Login to example.com'. nodes: n1 operation web.get_dom url https://example.com/login; n2 operation form.autofill url https://example.com/login form_type login depends_on n1; n3 operation web.click_selector url https://example.com/login selector #submit depends_on n2. edges: n1->n2 depends_on, n2->n3 depends_on. Use procedure.create."
echo ""

echo "3) Execute the stored procedure by queueing each step"
post_msg "Execute the stored 'Example Login' procedure by using dag.execute on the stored procedure UUID and queue each tool command."
echo ""

echo "4) Recite the stored steps"
post_msg "Recite the stored login procedure steps for example.com."
echo ""

echo "Done. Inspect log_dump.txt or /ui for details."
