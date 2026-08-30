#!/usr/bin/env bash
set -euo pipefail

DEST_IP="${OWL_CAM_DEST_IP:-100.116.197.91}"
DEST_PORT="${OWL_CAM_DEST_PORT:-5000}"

WIDTH="${OWL_CAM_WIDTH:-1920}"
HEIGHT="${OWL_CAM_HEIGHT:-1080}"
FRAMERATE="${OWL_CAM_FRAMERATE:-30}"
STREAM_HOST="${OWL_CAM_STREAM_HOST:-owlcam.tail31318f.ts.net}"

force=false

usage() {
  cat <<'EOF'
Usage: start_stream.sh [--force]

Sends the camera to one machine as MPEG-TS over UDP, for VLC. This bypasses
MediaMTX, so the web page has no stream while it runs.

  --force   Stop the owlcam-stream service and take the camera anyway.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) force=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

# The sensor accepts one consumer. Taking it from the service does not fail
# loudly: the web page just reports no stream on path 'owl', which is
# indistinguishable from the camera being off, while systemd restarts the unit
# every few seconds forever.
if systemctl --user is-active owlcam-stream.service >/dev/null 2>&1; then
  if ! "${force}"; then
    cat >&2 <<EOF
Refusing to start: the owlcam-stream service is running and owns the camera.

Starting this would take the sensor, and the web page would go dark while
systemd restarts the service in a loop.

To watch in VLC without stopping the web page, open the same HLS feed the
browser uses. MediaMTX serves any number of readers at once:

  https://${STREAM_HOST}/owl/index.m3u8

To take the camera anyway:

  systemctl --user stop owlcam-stream    # or pass --force
EOF
    exit 1
  fi
  printf 'Stopping owlcam-stream to take the camera...\n'
  systemctl --user stop owlcam-stream.service
  sleep 2
fi

command -v rpicam-vid >/dev/null 2>&1 || {
  printf 'ERROR: rpicam-vid is not installed.\n' >&2
  exit 1
}

command -v ffmpeg >/dev/null 2>&1 || {
  printf 'ERROR: ffmpeg is not installed.\n' >&2
  exit 1
}

printf 'Starting OwlCam camera stream\n'
printf 'Resolution: %sx%s\n' "${WIDTH}" "${HEIGHT}"
printf 'Framerate:  %s fps\n' "${FRAMERATE}"
printf 'Destination: udp://%s:%s\n' "${DEST_IP}" "${DEST_PORT}"
printf '\n'

rpicam-vid \
  -t 0 \
  -n \
  --width "${WIDTH}" \
  --height "${HEIGHT}" \
  --framerate "${FRAMERATE}" \
  --inline \
  --codec h264 \
  -o - \
| ffmpeg \
  -f h264 \
  -framerate "${FRAMERATE}" \
  -i - \
  -c:v copy \
  -fflags +genpts \
  -muxdelay 0 \
  -f mpegts \
  "udp://${DEST_IP}:${DEST_PORT}?pkt_size=1316"
