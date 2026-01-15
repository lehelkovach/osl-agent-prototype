#!/bin/bash
# Start the KnowShowGo service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Default port
PORT="${KNOWSHOWGO_PORT:-8001}"
HOST="${KNOWSHOWGO_HOST:-0.0.0.0}"

echo "Starting KnowShowGo service on $HOST:$PORT..."

# Run the service
poetry run python -c "
import sys
sys.path.insert(0, '.')
from services.knowshowgo.service import run_service
run_service(host='$HOST', port=$PORT)
"
