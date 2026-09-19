#!/usr/bin/env bash
set -euo pipefail

readonly DEVICE="${OWLCAM_USB_DEVICE:-/dev/video2}"
readonly WIDTH="${OWLCAM_USB_WIDTH:-1280}"
readonly HEIGHT="${OWLCAM_USB_HEIGHT:-720}"
readonly FRAMERATE="${OWLCAM_USB_FRAMERATE:-20}"
readonly BITRATE="${OWLCAM_USB_BITRATE:-2000000}"
readonly RTSP_URL="${OWLCAM_USB_RTSP_URL:-rtsp://127.0.0.1:8554/owl2}"

if [[ ! -e "${DEVICE}" ]]; then
  printf 'USB camera device missing: %s\n' "${DEVICE}" >&2
  exit 1
fi

exec ffmpeg \
  -hide_banner \
  -loglevel warning \
  -f v4l2 \
  -input_format mjpeg \
  -video_size "${WIDTH}x${HEIGHT}" \
  -framerate "${FRAMERATE}" \
  -i "${DEVICE}" \
  -an \
  -c:v h264_v4l2m2m \
  -b:v "${BITRATE}" \
  -g "$((FRAMERATE * 2))" \
  -pix_fmt yuv420p \
  -f rtsp \
  "${RTSP_URL}"
