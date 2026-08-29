#!/usr/bin/env bash
set -euo pipefail

readonly WIDTH="${OWLCAM_WIDTH:-1920}"
readonly HEIGHT="${OWLCAM_HEIGHT:-1080}"
readonly FRAMERATE="${OWLCAM_FRAMERATE:-30}"
readonly RTSP_URL="${OWLCAM_RTSP_URL:-rtsp://127.0.0.1:8554/owl}"

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
  -hide_banner \
  -loglevel warning \
  -f h264 \
  -framerate "${FRAMERATE}" \
  -i - \
  -c:v copy \
  -fflags +genpts \
  -f rtsp \
  "${RTSP_URL}"
