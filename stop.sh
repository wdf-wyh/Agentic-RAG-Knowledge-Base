#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
PORTS=(8002 8000 5175 5173)
STOPPED=0

stop_pid() {
  local pid="$1"
  local reason="$2"
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    return
  fi
  echo "Stopping PID $pid - $reason"
  kill "$pid" 2>/dev/null || true
  sleep 0.3
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  STOPPED=$((STOPPED + 1))
}

echo "[1/3] Stopping listeners on ports: ${PORTS[*]}..."
for port in "${PORTS[@]}"; do
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    pids="$(fuser "${port}/tcp" 2>/dev/null || true)"
  else
    pids=""
  fi
  for pid in $pids; do
    stop_pid "$pid" "port $port"
  done
done

echo "[2/3] Stopping project backend/frontend processes..."
if command -v pgrep >/dev/null 2>&1; then
  while IFS= read -r pid; do
    [ -n "$pid" ] && stop_pid "$pid" "run_api.py"
  done < <(pgrep -f "$ROOT_DIR/.*run_api\\.py|python .*run_api\\.py" 2>/dev/null || true)

  while IFS= read -r pid; do
    [ -n "$pid" ] && stop_pid "$pid" "vite/npm"
  done < <(pgrep -f "$FRONTEND_DIR.*(vite|npm run dev)|node .*vite" 2>/dev/null || true)
fi

echo "[3/3] Rechecking ports..."
still_up=()
for port in "${PORTS[@]}"; do
  if command -v lsof >/dev/null 2>&1; then
    if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      still_up+=("$port")
    fi
  fi
done

echo
if [ "$STOPPED" -eq 0 ] && [ "${#still_up[@]}" -eq 0 ]; then
  echo "Nothing to stop. Services were not running."
elif [ "${#still_up[@]}" -gt 0 ]; then
  echo "Stopped $STOPPED process(es), but ports still in use: ${still_up[*]}"
  exit 1
else
  echo "Stopped $STOPPED process(es). Backend/frontend are down."
fi
