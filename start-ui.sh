#!/usr/bin/env bash
# Start API + open browser UI at http://127.0.0.1:8765/
set -euo pipefail
cd "$(dirname "$0")"

PORT="${AGENT_PORT:-8765}"

if lsof -i ":$PORT" >/dev/null 2>&1; then
  echo "Stopping old server on port $PORT..."
  kill "$(lsof -t -i ":$PORT")" 2>/dev/null || true
  sleep 1
fi

echo "Starting server on port $PORT..."
python3 server.py &
sleep 1

URL="http://127.0.0.1:$PORT/"
echo "Open in browser: $URL"
if command -v open >/dev/null 2>&1; then
  open "$URL"
fi
wait
