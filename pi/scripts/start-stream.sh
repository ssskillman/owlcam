#!/usr/bin/env bash
set -euo pipefail

readonly WIDTH="${OWLCAM_WIDTH:-1920}"
readonly HEIGHT="${OWLCAM_HEIGHT:-1080}"
readonly FRAMERATE="${OWLCAM_FRAMERATE:-30}"
readonly RTSP_URL="${OWLCAM_RTSP_URL:-rtsp://127.0.0.1:8554/owl}"
# Every viewer pulls the full bitrate. The rpicam-vid default of roughly
# 10 Mbps saturates a home upload link with only a few watchers.
readonly BITRATE="${OWLCAM_BITRATE:-2500000}"
# Nest audio rides the same publish so viewers get one synchronised stream.
# Set OWLCAM_AUDIO_DEVICE empty to publish video only.
readonly AUDIO_DEVICE="${OWLCAM_AUDIO_DEVICE:-owlmic}"
readonly AUDIO_BITRATE="${OWLCAM_AUDIO_BITRATE:-64k}"

# A missing, unsoldered, or busy microphone must not take the video feed down
# with it, so the device is probed before ffmpeg commits to opening it.
audio_input=()
audio_output=()
if [[ -n "${AUDIO_DEVICE}" ]] && arecord -D "${AUDIO_DEVICE}" \
  -c 1 -r 48000 -f S32_LE -d 1 /dev/null >/dev/null 2>&1; then
  audio_input=(-f alsa -ar 48000 -i "${AUDIO_DEVICE}")
  audio_output=(-c:a aac -b:a "${AUDIO_BITRATE}" -ac 1 -ar 48000)
else
  printf 'owlcam: no usable microphone at "%s"; publishing video only\n' \
    "${AUDIO_DEVICE}" >&2
fi

rpicam-vid \
  -t 0 \
  -n \
  --width "${WIDTH}" \
  --height "${HEIGHT}" \
  --framerate "${FRAMERATE}" \
  --bitrate "${BITRATE}" \
  --inline \
  --codec h264 \
  -o - \
| ffmpeg \
  -hide_banner \
  -loglevel warning \
  -f h264 \
  -framerate "${FRAMERATE}" \
  -use_wallclock_as_timestamps 1 \
  -i - \
  "${audio_input[@]}" \
  -c:v copy \
  "${audio_output[@]}" \
  -fflags +genpts \
  -f rtsp \
  "${RTSP_URL}"
