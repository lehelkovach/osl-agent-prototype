#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH}"
cd "${ROOT_DIR}"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
URL="http://${HOST}:${PORT}/ui"

# Test mode for CI: just import and exit
if [[ "${RUN_AGENT_TEST}" == "1" ]]; then
  python3 - <<PY
import importlib
import sys
try:
    importlib.import_module("src.personal_assistant.service")
    print("import_ok")
    sys.exit(0)
except Exception as exc:
    print(f"import_failed: {exc}")
    sys.exit(1)
PY
  exit $?
fi

echo "Starting agent service on ${HOST}:${PORT}..."
uvicorn src.personal_assistant.service:app --host "${HOST}" --port "${PORT}" --reload &
PID=$!

sleep 2
echo "Opening UI at ${URL}"
python3 - <<PY
import webbrowser
url = "${URL}"
try:
    webbrowser.open(url)
except Exception as exc:
    print(f"Could not open browser: {exc}")
PY

trap "kill ${PID}" EXIT
wait ${PID}
