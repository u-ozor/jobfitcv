#!/bin/bash
# start.sh — start the API in the background

PID_FILE=".api.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
  echo "[api] already running (pid $(cat $PID_FILE))"
  exit 0
fi

if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

# Defaults to 8000 if PORT isn't set in .env. If you change this, you must
# also update BASE_URL in extension/config.js to match, then reload the
# extension in chrome://extensions.
PORT="${PORT:-8000}"

kratos/bin/python -m uvicorn app.api.main:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --reload \
  >> logs/api.log 2>&1 &

echo $! > "$PID_FILE"
echo "[api] started (pid $(cat $PID_FILE)) — logs/api.log"
