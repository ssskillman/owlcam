#!/usr/bin/env bash
set -euo pipefail

readonly DEVICE="${OWLCAM_USB_DEVICE:-/dev/video2}"
readonly WIDTH="${OWLCAM_USB_WIDTH:-1280}"
readonly HEIGHT="${OWLCAM_USB_HEIGHT:-720}"
readonly FRAMERATE="${OWLCAM_USB_FRAMERATE:-20}"
readonly BITRATE="${OWLCAM_USB_BITRATE:-2000000}"
readonly RTSP_URL="${OWLCAM_USB_RTSP_URL:-rtsp://127.0.0.1:8554/owl2}"
# The nest microphone is shared, so this publish carries the same audio as the
# nest camera. owlmic is a dsnoop device; the raw card allows only one reader.
readonly AUDIO_DEVICE="${OWLCAM_AUDIO_DEVICE:-owlmic}"
readonly AUDIO_BITRATE="${OWLCAM_AUDIO_BITRATE:-64k}"

if [[ ! -e "${DEVICE}" ]]; then
  printf 'USB camera device missing: %s\n' "${DEVICE}" >&2
  exit 1
fi

# A missing or busy microphone must not take this feed down with it.
audio_input=(-an)
audio_output=()
if [[ -n "${AUDIO_DEVICE}" ]] && arecord -D "${AUDIO_DEVICE}" \
  -c 1 -r 48000 -f S32_LE -d 1 /dev/null >/dev/null 2>&1; then
  audio_input=(-f alsa -ar 48000 -i "${AUDIO_DEVICE}")
  audio_output=(-c:a aac -b:a "${AUDIO_BITRATE}" -ac 1 -ar 48000)
else
  printf 'owlcam: no usable microphone at "%s"; publishing video only\n' \
    "${AUDIO_DEVICE}" >&2
fi

exec ffmpeg \
  -hide_banner \
  -loglevel warning \
  -f v4l2 \
  -input_format mjpeg \
  -video_size "${WIDTH}x${HEIGHT}" \
  -framerate "${FRAMERATE}" \
  -use_wallclock_as_timestamps 1 \
  -i "${DEVICE}" \
  "${audio_input[@]}" \
  -c:v h264_v4l2m2m \
  -b:v "${BITRATE}" \
  -g "$((FRAMERATE * 2))" \
  -pix_fmt yuv420p \
  "${audio_output[@]}" \
  -f rtsp \
  "${RTSP_URL}"
