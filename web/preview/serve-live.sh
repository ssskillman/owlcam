#!/usr/bin/env bash
# Preview the built site on this Mac against the live Pi stream.
#
# MediaMTX binds to loopback on the Pi, so the stream arrives through an SSH
# tunnel and is proxied under the same origin as the page. One origin is not
# cosmetic here: the page fetches /owl/index.m3u8 relatively, and Web Audio
# refuses to meter a cross-origin media element.
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SITE="${ROOT}/public"
readonly PORT="${OWLCAM_PREVIEW_PORT:-8770}"
readonly HLS_PORT="${OWLCAM_PREVIEW_HLS_PORT:-8888}"
readonly DIAGNOSTICS_PORT="${OWLCAM_PREVIEW_DIAGNOSTICS_PORT:-18765}"
readonly TARGET="${OWLCAM_SSH_TARGET:-shawn@100.123.8.55}"
readonly PID_TUNNEL="${ROOT}/preview/.live-tunnel.pid"
readonly PID_SERVER="${ROOT}/preview/.live-server.pid"
readonly LOG="${ROOT}/preview/.live-server.log"

stop_one() {
  local pidfile="$1"
  if [[ -f "${pidfile}" ]]; then
    kill "$(cat "${pidfile}")" 2>/dev/null || true
    rm -f "${pidfile}"
  fi
}

stop_all() {
  stop_one "${PID_TUNNEL}"
  stop_one "${PID_SERVER}"
}

if [[ "${1:-}" == "--stop" ]]; then
  stop_all
  printf 'Preview stopped.\n'
  exit 0
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  printf 'Usage: %s [--stop]\n\n' "$0"
  printf 'Serves web/public at http://127.0.0.1:%s with /owl proxied from the Pi.\n' "${PORT}"
  printf 'Run "make web-build" first.\n'
  exit 0
fi

if [[ ! -f "${SITE}/index.html" ]]; then
  printf 'No built site at %s. Run "make web-build" first.\n' "${SITE}" >&2
  exit 1
fi

stop_all

ssh_opts=(-o BatchMode=yes -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes)
if [[ -n "${OWLCAM_SSH_IDENTITY:-}" ]]; then
  ssh_opts+=(-i "${OWLCAM_SSH_IDENTITY}")
fi

# setsid, not just "&": a backgrounded child stays in this shell's process
# group and dies with it, which looks exactly like "localhost is broken".
python3 -c "
import os, sys
os.setsid()
os.execvp('ssh', sys.argv[1:])
" ssh "${ssh_opts[@]}" -N \
  -L "${HLS_PORT}:127.0.0.1:8888" \
  -L "${DIAGNOSTICS_PORT}:127.0.0.1:8765" \
  "${TARGET}" >>"${LOG}" 2>&1 &
echo $! >"${PID_TUNNEL}"

python3 -c "
import os, sys
os.setsid()
os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
" "${ROOT}/preview/live_proxy.py" "${SITE}" "${PORT}" "${HLS_PORT}" "${DIAGNOSTICS_PORT}" >>"${LOG}" 2>&1 &
echo $! >"${PID_SERVER}"

sleep 1.5
code="$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://127.0.0.1:${PORT}/" || true)"
if [[ "${code}" != "200" ]]; then
  printf 'Preview server did not answer (HTTP %s). See %s\n' "${code:-none}" "${LOG}" >&2
  exit 1
fi

printf 'Live preview: http://127.0.0.1:%s/\n' "${PORT}"
printf 'Stop with:    %s --stop\n' "$0"
