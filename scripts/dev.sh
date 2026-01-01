#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export PYTHONPATH="${ROOT}:${PYTHONPATH}"
# Defaults: prefer real OpenAI if key is set; else local/fake
if [[ -z "${OPENAI_API_KEY}" ]]; then
  export EMBEDDING_BACKEND="${EMBEDDING_BACKEND:-local}"
  export USE_FAKE_OPENAI="${USE_FAKE_OPENAI:-1}"
fi

if [[ "${INSTALL_EMBEDDER}" == "1" ]]; then
  echo "Checking sentence-transformers..."
  ./scripts/install_local_embedder.sh || true
else
  echo "Skipping sentence-transformers install (set INSTALL_EMBEDDER=1 to enable)."
fi

if [[ "${SKIP_TESTS}" == "1" ]]; then
  echo "Skipping tests (set SKIP_TESTS=0 to run)."
else
  echo "Running tests..."
  pytest -q
fi

echo "Starting service..."
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
LOG_FILE="${AGENT_LOG_FILE:-}"
CMD="uvicorn src.personal_assistant.service:app --host ${HOST} --port ${PORT}"
if [ -n "$LOG_FILE" ]; then
  echo "Logging to $LOG_FILE"
fi
echo "Run: ${CMD}"
${CMD}
