#!/usr/bin/env bash
# Phase 1 — one still from loopback RTSP and POST to the identify API.
# Run on the Pi. Set OWLCAM_IDENTIFY_URL to the PC Funnel origin, e.g.:
#   OWLCAM_IDENTIFY_URL=https://penns-gaming-pc.tail31318f.ts.net:8443/api/animal-identification
set -euo pipefail

readonly RTSP_URL="${OWLCAM_RTSP_URL:-rtsp://127.0.0.1:8554/owl}"
readonly IDENTIFY_URL="${OWLCAM_IDENTIFY_URL:-}"
readonly STILL="${OWLCAM_E2E_STILL:-/tmp/owlcam-feed-e2e.jpg}"

if [[ -z "${IDENTIFY_URL}" ]]; then
  printf 'Set OWLCAM_IDENTIFY_URL to the inference host POST endpoint.\n' >&2
  exit 2
fi

command -v ffmpeg >/dev/null || { printf 'ffmpeg required\n' >&2; exit 1; }
command -v curl >/dev/null || { printf 'curl required\n' >&2; exit 1; }

ffmpeg -y -loglevel error -rtsp_transport tcp -i "${RTSP_URL}" \
  -frames:v 1 -update 1 -q:v 2 "${STILL}"

printf 'Still written: %s (%s bytes)\n' "${STILL}" "$(wc -c <"${STILL}" | tr -d ' ')"

curl -sS -m 90 \
  -H 'X-OwlCam-Source: feed_watcher' \
  -F "images=@${STILL}" \
  "${IDENTIFY_URL}" | python3 -m json.tool

printf '\nPhase 1 complete. Expect is_unknown:true on an empty perch.\n'
