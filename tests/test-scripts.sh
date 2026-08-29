#!/usr/bin/env bash
set -euo pipefail

readonly REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

deploy_output="$("${REPO_ROOT}/pi/scripts/deploy.sh" --dry-run)"
[[ "${deploy_output}" == *"Would stage"* ]] \
  || fail "deploy dry-run did not describe staged files"
[[ "${deploy_output}" == *"/deploy/pi/scripts/"* ]] \
  || fail "deploy layout would break repository-relative script paths"
[[ "${deploy_output}" == *"/deploy/scripts/"* ]] \
  || fail "deploy dry-run does not stage UDP scripts/"
[[ "${deploy_output}" != *"Would back up and install"* ]] \
  || fail "deploy dry-run installs configuration without opt-in"

config_output="$("${REPO_ROOT}/pi/scripts/deploy.sh" --dry-run --install-config)"
[[ "${config_output}" == *"Would back up and install"* ]] \
  || fail "explicit configuration install was not described"

if "${REPO_ROOT}/pi/scripts/deploy.sh" --not-an-option >/dev/null 2>&1; then
  fail "deploy accepted an unknown option"
fi

stream_script="${REPO_ROOT}/pi/scripts/start-stream.sh"
grep -F -- "--inline" "${stream_script}" >/dev/null \
  || fail "stream script is missing inline headers"
grep -F -- 'WIDTH="${OWLCAM_WIDTH:-1920}"' "${stream_script}" >/dev/null \
  || fail "stream script default width changed"
grep -F -- 'HEIGHT="${OWLCAM_HEIGHT:-1080}"' "${stream_script}" >/dev/null \
  || fail "stream script default height changed"
grep -F -- 'FRAMERATE="${OWLCAM_FRAMERATE:-30}"' "${stream_script}" >/dev/null \
  || fail "stream script default frame rate changed"
grep -F -- 'BITRATE="${OWLCAM_BITRATE:-2500000}"' "${stream_script}" >/dev/null \
  || fail "stream script default bitrate changed"
grep -F -- '--bitrate "${BITRATE}"' "${stream_script}" >/dev/null \
  || fail "stream script does not cap the encoder bitrate"
grep -F -- "-c:v copy" "${stream_script}" >/dev/null \
  || fail "stream script would re-encode video"
grep -F -- "-fflags +genpts" "${stream_script}" >/dev/null \
  || fail "stream script is missing generated timestamps"
grep -F -- "rtsp://127.0.0.1:8554/owl" "${stream_script}" >/dev/null \
  || fail "stream script default RTSP path changed"

serve_script="${REPO_ROOT}/pi/scripts/serve-stream.sh"
[[ -x "${serve_script}" ]] || fail "serve script is missing or not executable"

serve_help="$("${serve_script}" --help)"
[[ "${serve_help}" == *"Tailnet devices only"* ]] \
  || fail "serve help does not state the private default"
[[ "${serve_help}" == *"Anyone with the URL can watch"* ]] \
  || fail "serve help does not warn that --public is internet-facing"

if "${serve_script}" --not-an-option >/dev/null 2>&1; then
  fail "serve script accepted an unknown option"
fi

grep -F -- "expose_mode=serve" "${serve_script}" >/dev/null \
  || fail "serve script does not default to private Tailscale Serve"
grep -F -- "tailscale funnel --bg" "${serve_script}" >/dev/null \
  || fail "serve script cannot publish publicly on request"
awk '/--public\) expose_mode=funnel/ { found = 1 } END { exit !found }' \
  "${serve_script}" \
  || fail "serve script enables Funnel without the --public opt-in"
grep -F -- "pgrep -f 'rpicam-vid'" "${serve_script}" >/dev/null \
  || fail "serve script would start a second camera capture"

udp_script="${REPO_ROOT}/scripts/start_stream.sh"
[[ -x "${udp_script}" ]] || fail "UDP stream script is missing or not executable"
grep -F -- 'DEST_IP="${OWL_CAM_DEST_IP:-100.116.197.91}"' "${udp_script}" >/dev/null \
  || fail "UDP script default destination IP changed"
grep -F -- 'DEST_PORT="${OWL_CAM_DEST_PORT:-5000}"' "${udp_script}" >/dev/null \
  || fail "UDP script default destination port changed"
grep -F -- 'WIDTH="${OWL_CAM_WIDTH:-1920}"' "${udp_script}" >/dev/null \
  || fail "UDP script default width changed"
grep -F -- 'HEIGHT="${OWL_CAM_HEIGHT:-1080}"' "${udp_script}" >/dev/null \
  || fail "UDP script default height changed"
grep -F -- 'FRAMERATE="${OWL_CAM_FRAMERATE:-30}"' "${udp_script}" >/dev/null \
  || fail "UDP script default frame rate changed"
grep -F -- "--inline" "${udp_script}" >/dev/null \
  || fail "UDP script is missing inline headers"
grep -F -- "-c:v copy" "${udp_script}" >/dev/null \
  || fail "UDP script would re-encode video"
grep -F -- "-muxdelay 0" "${udp_script}" >/dev/null \
  || fail "UDP script is missing muxdelay 0"
grep -F -- '-f mpegts' "${udp_script}" >/dev/null \
  || fail "UDP script is not MPEG-TS"
grep -F -- 'udp://${DEST_IP}:${DEST_PORT}?pkt_size=1316' "${udp_script}" >/dev/null \
  || fail "UDP script destination or packet size changed"

printf 'Script checks passed.\n'
