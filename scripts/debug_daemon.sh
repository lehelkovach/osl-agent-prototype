#!/usr/bin/env bash
set -euo pipefail

# Debug helper:
# - start: runs the agent with reload, logs to console + log file
# - optional: stop on first ERROR/Exception/Traceback and snapshot logs
# - stop/status/clear-log commands
#
# Usage:
#   ./scripts/debug_daemon.sh start [--test]
#   ./scripts/debug_daemon.sh stop
#   ./scripts/debug_daemon.sh status
#   ./scripts/debug_daemon.sh clear-log
#
# Config (env):
#   HOST (default 127.0.0.1), PORT (8000)
#   AGENT_LOG_FILE (default ./log_dump.txt)
#   STOP_ON_ERROR=1 to auto-stop on first error and snapshot the tail
#   SNAP_LINES (default 300) number of lines to capture on error
#   LOG_WEBHOOK optional: POST snapshots to this URL (same as watch_agent_logs.sh)
#   OPENAI_API_KEY set => real OpenAI; unset => EMBEDDING_BACKEND=local, USE_FAKE_OPENAI=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
LOGFILE="${AGENT_LOG_FILE:-${ROOT}/log_dump.txt}"
PIDFILE="${ROOT}/scripts/.debug_agent.pid"
MONPIDFILE="${ROOT}/scripts/.debug_monitor.pid"
STOP_ON_ERROR="${STOP_ON_ERROR:-0}"
SNAP_LINES="${SNAP_LINES:-300}"
SNAPDIR="${ROOT}/log_snapshots"
LOG_WEBHOOK="${LOG_WEBHOOK:-}"
LOG_LEVEL="${LOG_LEVEL:-info}"
AGENT_CONFIG="${AGENT_CONFIG:-}"

mkdir -p "${SNAPDIR}"
mkdir -p "$(dirname "${LOGFILE}")"
touch "${LOGFILE}"

prefer_fake_if_no_key() {
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    export EMBEDDING_BACKEND="${EMBEDDING_BACKEND:-local}"
    export USE_FAKE_OPENAI="${USE_FAKE_OPENAI:-1}"
  fi
}

is_running() {
  [[ -f "${PIDFILE}" ]] || return 1
  local pid
  pid=$(cat "${PIDFILE}")
  if ps -p "${pid}" > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

is_monitor_running() {
  [[ -f "${MONPIDFILE}" ]] || return 1
  local pid
  pid=$(cat "${MONPIDFILE}")
  if ps -p "${pid}" > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

start_agent() {
  if is_running; then
    echo "Agent already running (pid $(cat "${PIDFILE}"))."
    exit 0
  fi
  prefer_fake_if_no_key
  export AGENT_LOG_FILE="${LOGFILE}"
  echo "Starting agent on ${HOST}:${PORT}"
  echo "Logging to ${LOGFILE}"
  args=(--host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}")
  if [[ "${DEBUG:-0}" == "1" || "${DEBUG:-}" == "true" ]]; then
    args+=(--debug)
  fi
  if [[ -n "${AGENT_CONFIG}" ]]; then
    args+=(--config "${AGENT_CONFIG}")
  fi
  (
    PYTHONUNBUFFERED=1 poetry run python -m src.personal_assistant.service "${args[@]}"
  ) > >(tee -a "${LOGFILE}") 2> >(tee -a "${LOGFILE}" >&2) &
  local pid=$!
  echo "${pid}" > "${PIDFILE}"
  echo "Agent pid: ${pid}"

  if [[ "${STOP_ON_ERROR}" == "1" ]]; then
    start_monitor "${pid}"
  fi
}

start_monitor() {
  local target_pid="$1"
  if is_monitor_running; then
    echo "Monitor already running (pid $(cat "${MONPIDFILE}"))."
    return
  fi
  echo "Starting error monitor (stop on first error)..."
  (
    tail -F "${LOGFILE}" | while IFS= read -r line; do
      if echo "${line}" | grep -E -q "ERROR|Exception|Traceback"; then
        ts="$(date +%Y%m%d_%H%M%S)"
        snap="${SNAPDIR}/error_${ts}.log"
        tail -n "${SNAP_LINES}" "${LOGFILE}" > "${snap}"
        echo "Captured error snapshot: ${snap}"
        if [[ -n "${LOG_WEBHOOK}" ]]; then
          curl -sS -X POST "${LOG_WEBHOOK}" \
            -H "Content-Type: text/plain" \
            --data-binary @"${snap}" \
            || echo "Webhook post failed for ${snap}"
        fi
        echo "Stopping agent (pid ${target_pid}) due to error..."
        kill "${target_pid}" 2>/dev/null || true
        exit 0
      fi
    done
  ) &
  echo $! > "${MONPIDFILE}"
}

stop_agent() {
  if is_monitor_running; then
    kill "$(cat "${MONPIDFILE}")" 2>/dev/null || true
    rm -f "${MONPIDFILE}"
  fi
  if is_running; then
    local pid
    pid=$(cat "${PIDFILE}")
    echo "Stopping agent pid ${pid}..."
    kill "${pid}" 2>/dev/null || true
    rm -f "${PIDFILE}"
  else
    echo "Agent not running."
  fi
}

status_agent() {
  if is_running; then
    echo "Agent running (pid $(cat "${PIDFILE}")), log: ${LOGFILE}"
  else
    echo "Agent not running."
  fi
  if is_monitor_running; then
    echo "Monitor running (pid $(cat "${MONPIDFILE}"))."
  fi
}

clear_log() {
  : > "${LOGFILE}"
  echo "Cleared ${LOGFILE}"
}

case "${1:-}" in
  start)
    if [[ "${2:-}" == "--test" ]]; then
      echo "Running test suite before starting agent..."
      if ! poetry run pytest -q; then
        echo "Tests failed; not starting agent."
        exit 1
      fi
      echo "Tests passed."
    fi
    start_agent
    ;;
  stop)
    stop_agent
    ;;
  status)
    status_agent
    ;;
  clear-log)
    clear_log
    ;;
  *)
    cat <<EOF
Usage: $0 {start|stop|status|clear-log}
Env:
  HOST, PORT, AGENT_LOG_FILE, STOP_ON_ERROR (default 0), SNAP_LINES (300)
  LOG_WEBHOOK (optional), OPENAI_API_KEY (if set uses real OpenAI)
EOF
    exit 1
    ;;
esac
