#!/usr/bin/env bash
set -euo pipefail

# Minimal supervisor: runs the agent with reload, restarts on exit/crash,
# and tails the log for quick diagnosis.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export PYTHONPATH="${ROOT}:${PYTHONPATH}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
AGENT_LOG_FILE="${AGENT_LOG_FILE:-${ROOT}/agent.log}"
RESTART_DELAY="${RESTART_DELAY:-2}"

# Prefer real OpenAI if key is set; else local/fake.
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  export EMBEDDING_BACKEND="${EMBEDDING_BACKEND:-local}"
  export USE_FAKE_OPENAI="${USE_FAKE_OPENAI:-1}"
fi

touch "${AGENT_LOG_FILE}"
echo "Supervising agent on ${HOST}:${PORT}, logging to ${AGENT_LOG_FILE}"
echo "Ctrl+C to stop."

tail -f "${AGENT_LOG_FILE}" &
TAIL_PID=$!

cleanup() {
  kill "${TAIL_PID}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

while true; do
  echo "Starting agent..." | tee -a "${AGENT_LOG_FILE}"
  uvicorn src.personal_assistant.service:app --host "${HOST}" --port "${PORT}" --reload >> "${AGENT_LOG_FILE}" 2>&1 || true
  echo "Agent exited. Restarting in ${RESTART_DELAY}s..." | tee -a "${AGENT_LOG_FILE}"
  sleep "${RESTART_DELAY}"
done
