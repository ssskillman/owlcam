#!/usr/bin/env bash
set -euo pipefail

DEST_IP="${OWL_CAM_DEST_IP:-100.116.197.91}"
DEST_PORT="${OWL_CAM_DEST_PORT:-5000}"

WIDTH="${OWL_CAM_WIDTH:-1920}"
HEIGHT="${OWL_CAM_HEIGHT:-1080}"
FRAMERATE="${OWL_CAM_FRAMERATE:-30}"

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
