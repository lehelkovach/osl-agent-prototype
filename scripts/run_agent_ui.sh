#!/usr/bin/env bash
set -e

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
URL="http://${HOST}:${PORT}/ui"

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
