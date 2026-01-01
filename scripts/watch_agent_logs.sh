#!/usr/bin/env bash
set -euo pipefail

# Stream agent logs and auto-snapshot the last N lines when errors appear.
# Useful for quickly sharing a reproducible log snippet.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGFILE="${AGENT_LOG_FILE:-${ROOT}/agent.log}"
SNAPDIR="${SNAPDIR:-${ROOT}/log_snapshots}"
TAIL_LINES="${TAIL_LINES:-300}"
LOG_WEBHOOK="${LOG_WEBHOOK:-}"

mkdir -p "${SNAPDIR}"
touch "${LOGFILE}"

echo "Watching ${LOGFILE} (snapshots to ${SNAPDIR}, ${TAIL_LINES} lines per snapshot)"
echo "Press Ctrl+C to stop."

tail -F "${LOGFILE}" | while IFS= read -r line; do
  echo "${line}"
  if echo "${line}" | grep -E -q "ERROR|Exception|Traceback"; then
    ts="$(date +%Y%m%d_%H%M%S)"
    snap="${SNAPDIR}/error_${ts}.log"
    tail -n "${TAIL_LINES}" "${LOGFILE}" > "${snap}"
    echo "Captured error snapshot: ${snap}"
    if [[ -n "${LOG_WEBHOOK}" ]]; then
      curl -sS -X POST "${LOG_WEBHOOK}" \
        -H "Content-Type: text/plain" \
        --data-binary @"${snap}" \
        || echo "Webhook post failed for ${snap}"
    fi
  fi
done
