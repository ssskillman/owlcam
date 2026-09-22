#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID1="${ROOT}/preview/.server-8771.pid"
PID2="${ROOT}/preview/.server-8772.pid"
PID3="${ROOT}/preview/.server-8773.pid"
LOG1="${ROOT}/preview/.server-8771.log"
LOG2="${ROOT}/preview/.server-8772.log"
LOG3="${ROOT}/preview/.server-8773.log"

stop_one() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile"
  fi
}

for f in "$PID1" "$PID2" "$PID3"; do stop_one "$f"; done

start_one() {
  local port="$1"
  local pidfile="$2"
  local log="$3"
  python3 -c "
import os, sys
os.chdir(sys.argv[1])
os.setsid()
os.execv(sys.executable, [sys.executable, '-m', 'http.server', str(sys.argv[2]), '--bind', '127.0.0.1'])
" "$ROOT" "$port" >>"$log" 2>&1 &
  echo $! >"$pidfile"
}

start_one 8771 "$PID1" "$LOG1"
start_one 8772 "$PID2" "$LOG2"
start_one 8773 "$PID3" "$LOG3"
sleep 0.4
printf 'A whisper rail:  http://127.0.0.1:8771/preview/full-a-whisper-rail.html\n'
printf 'B inline stat:   http://127.0.0.1:8772/preview/full-b-inline-stat.html\n'
printf 'C ledger chip:   http://127.0.0.1:8773/preview/full-c-ledger-chip.html\n'
