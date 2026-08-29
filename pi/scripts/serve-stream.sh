#!/usr/bin/env bash
set -euo pipefail

# Brings the OwlCam live feed up on the Pi and publishes it over HTTPS.
#
# Private by default: only devices signed in to the tailnet can watch.
# --public switches to Tailscale Funnel, which exposes the feed to anyone
# on the internet who has the URL.

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly HLS_PORT="${OWLCAM_HLS_PORT:-8888}"
readonly STREAM_PATH="${OWLCAM_STREAM_PATH:-owl}"
readonly LOG_DIR="${OWLCAM_LOG_DIR:-/home/shawn/owlcam/logs}"

expose_mode=serve
teardown=false

usage() {
  cat <<'EOF'
Usage: serve-stream.sh [--public] [--stop]

  (default)  Publish over Tailscale Serve. Tailnet devices only.
  --public   Publish over Tailscale Funnel. Anyone with the URL can watch.
  --stop     Stop the camera, MediaMTX, and HTTPS publishing.

Optional environment:
  OWLCAM_HLS_PORT      MediaMTX HLS port, default 8888
  OWLCAM_STREAM_PATH   MediaMTX path name, default owl
  OWLCAM_LOG_DIR       log destination, default /home/shawn/owlcam/logs
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --public) expose_mode=funnel ;;
    --stop) teardown=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

require() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

require tailscale
require curl

if "${teardown}"; then
  tailscale funnel --https=443 off 2>/dev/null || true
  tailscale serve --https=443 off 2>/dev/null || true
  pkill -f 'rpicam-vid' 2>/dev/null || true
  pkill -f 'ffmpeg .*rtsp' 2>/dev/null || true
  pkill -x mediamtx 2>/dev/null || true
  printf 'OwlCam stream stopped.\n'
  exit 0
fi

require mediamtx
require rpicam-vid
require ffmpeg

mkdir -p "${LOG_DIR}"

# Two concurrent rpicam-vid processes fight over the sensor and both fail.
if pgrep -f 'rpicam-vid' >/dev/null 2>&1; then
  printf 'rpicam-vid is already running; leaving the existing capture alone.\n'
else
  if ! pgrep -x mediamtx >/dev/null 2>&1; then
    printf 'Starting MediaMTX...\n'
    setsid mediamtx >>"${LOG_DIR}/mediamtx.log" 2>&1 &
    sleep 3
  fi

  printf 'Starting camera capture...\n'
  setsid "${SCRIPT_DIR}/start-stream.sh" >>"${LOG_DIR}/capture.log" 2>&1 &
  sleep 5
fi

hls_url="http://127.0.0.1:${HLS_PORT}/${STREAM_PATH}/index.m3u8"
printf 'Waiting for local HLS at %s\n' "${hls_url}"
for _ in $(seq 1 20); do
  if curl -fsS -m 3 -o /dev/null "${hls_url}"; then
    local_ready=true
    break
  fi
  sleep 2
done

if [[ "${local_ready:-false}" != true ]]; then
  printf 'Local HLS never became ready. Check %s/*.log\n' "${LOG_DIR}" >&2
  exit 1
fi
printf 'Local HLS is serving.\n'

if [[ "${expose_mode}" == funnel ]]; then
  printf 'Publishing publicly over Tailscale Funnel...\n'
  tailscale serve --https=443 off 2>/dev/null || true
  tailscale funnel --bg --https=443 "http://127.0.0.1:${HLS_PORT}"
else
  printf 'Publishing privately over Tailscale Serve...\n'
  tailscale funnel --https=443 off 2>/dev/null || true
  tailscale serve --bg --https=443 "http://127.0.0.1:${HLS_PORT}"
fi

host="$(tailscale status --json | sed -n 's/.*"DNSName": *"\([^"]*\)\.".*/\1/p' | head -1)"
printf '\nOwlCam is publishing.\n'
printf 'Watch URL: https://%s/%s/index.m3u8\n' "${host}" "${STREAM_PATH}"
if [[ "${expose_mode}" == funnel ]]; then
  printf 'Exposure: PUBLIC. Anyone with this URL can watch.\n'
else
  printf 'Exposure: tailnet only. Sign in to Tailscale to watch.\n'
fi
