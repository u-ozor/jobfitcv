#!/bin/bash
# stop.sh — stop the background API process.
# --reload spawns a child worker under the reloader PID; killing only the
# parent can leave the child (and the port) alive, causing a silent bind
# failure on the next start.sh. This kills the whole process group, waits
# for it to actually exit, then force-clears the port as a final guarantee.

if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

PID_FILE=".api.pid"
PORT="${PORT:-8000}"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    # Negative PID = whole process group (reloader + its worker children).
    kill -- "-$PID" 2>/dev/null || kill "$PID" 2>/dev/null
    for i in 1 2 3 4 5; do
      kill -0 "$PID" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "$PID" 2>/dev/null; then
      kill -9 -- "-$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
    fi
    echo "[api] stopped (pid $PID)"
  else
    echo "[api] process $PID already gone"
  fi
  rm -f "$PID_FILE"
else
  echo "[api] no .api.pid found"
fi

# Final guarantee: nothing should be listening on $PORT after this script runs,
# regardless of whether the pid file was accurate.
LEFTOVER=$(lsof -ti:$PORT 2>/dev/null)
if [ -n "$LEFTOVER" ]; then
  echo "[api] clearing leftover process(es) on port $PORT: $LEFTOVER"
  echo "$LEFTOVER" | xargs -r kill -9
fi
