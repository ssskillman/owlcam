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
[[ "${deploy_output}" == *"/deploy/pi/systemd/"* ]] \
  || fail "deploy dry-run does not stage the systemd units the installer reads"
[[ "${deploy_output}" != *"Would back up and install"* ]] \
  || fail "deploy dry-run installs configuration without opt-in"
grep -F -- "--exclude '__pycache__'" "${REPO_ROOT}/pi/scripts/deploy.sh" >/dev/null \
  || fail "deploy sends Python bytecode caches to the Pi"

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

udp_help="$("${udp_script}" --help)"
[[ "${udp_help}" == *"bypasses"* ]] \
  || fail "UDP help does not warn that it bypasses MediaMTX"
[[ "${udp_help}" == *"--force"* ]] \
  || fail "UDP help does not document the override"

if "${udp_script}" --not-an-option >/dev/null 2>&1; then
  fail "UDP script accepted an unknown option"
fi

# Silently stealing the sensor from the service reads as a dead camera on the
# web page while systemd restarts the unit in a loop.
grep -F -- 'service_owns_camera' "${udp_script}" >/dev/null \
  || fail "UDP script does not check whether the service owns the camera"
# is-active reports failure while a unit is 'activating', which is where a
# thrashing unit spends most of its time, so that check alone lets the script
# through during exactly the situation the guard exists to prevent.
grep -F -- 'is-enabled owlcam-stream.service' "${udp_script}" >/dev/null \
  || fail "UDP guard misses an installed unit that is mid-restart"
grep -F -- 'activating' "${udp_script}" >/dev/null \
  || fail "UDP guard does not treat a restarting unit as owning the camera"
grep -F -- 'quitting VLC does not stop this script' "${udp_script}" >/dev/null \
  || fail "UDP script does not explain that closing the player leaves it running"
# Killing the unit's capture without stopping the unit just triggers
# Restart=always, and the two pipelines take turns knocking each other over.
grep -F -- 'systemctl --user stop owlcam-stream.service' "${udp_script}" >/dev/null \
  || fail "UDP --force does not stop the unit before taking the camera"
# A prompt with no terminal blocks forever under nohup, a unit, or piped SSH.
grep -F -- '[[ ! -t 0 ]]' "${udp_script}" >/dev/null \
  || fail "UDP script would block on a prompt with no terminal attached"
# pkill -f matches the script's own command line and can kill the caller.
if grep -E -- 'pkill .*-f "rpicam' "${udp_script}" >/dev/null 2>&1; then
  fail "UDP script matches rpicam on the full command line and can kill its own shell"
fi
[[ "${udp_help}" == *"--yes"* ]] \
  || fail "UDP help does not document the non-interactive flag"
grep -F -- 'Refusing to start' "${udp_script}" >/dev/null \
  || fail "UDP script does not refuse when the service owns the camera"
grep -F -- '/owl/index.m3u8' "${udp_script}" >/dev/null \
  || fail "UDP script does not offer the HLS URL as the non-destructive option"

install_script="${REPO_ROOT}/pi/scripts/install-services.sh"
[[ -x "${install_script}" ]] || fail "service installer is missing or not executable"

install_help="$("${install_script}" --help)"
[[ "${install_help}" == *"--uninstall"* ]] \
  || fail "installer help does not document removal"

if "${install_script}" --not-an-option >/dev/null 2>&1; then
  fail "installer accepted an unknown option"
fi

# User units stop with the last SSH session and never start at boot unless the
# account lingers, which defeats the point of installing them at all.
grep -F -- 'loginctl enable-linger' "${install_script}" >/dev/null \
  || fail "installer does not enable lingering for boot survival"
# The sensor takes one consumer, so a hand-started capture makes the unit
# restart forever instead of serving.
grep -F -- 'pkill -x rpicam-vid' "${install_script}" >/dev/null \
  || fail "installer does not release the sensor before starting the unit"
# "enable --now" leaves an already-active unit running the previous binary, so a
# reinstall of newly staged code silently keeps serving the old payload.
grep -F -- 'systemctl --user restart owlcam-diagnostics.service' "${install_script}" \
  >/dev/null \
  || fail "installer does not restart diagnostics onto the newly staged code"
grep -F -- 'curl -fsSL' "${install_script}" >/dev/null \
  || fail "installer health check must follow the MediaMTX cookie redirect"
grep -F -- 'owlcam-diagnostics.service' "${install_script}" >/dev/null \
  || fail "installer does not manage the diagnostics service"
grep -F -- '--set-path /diagnostics' "${install_script}" >/dev/null \
  || fail "installer does not add the private diagnostics route"

stream_unit="${REPO_ROOT}/pi/systemd/owlcam-stream.service"
mediamtx_unit="${REPO_ROOT}/pi/systemd/owlcam-mediamtx.service"
diagnostics_unit="${REPO_ROOT}/pi/systemd/owlcam-diagnostics.service"
[[ -r "${stream_unit}" ]] || fail "owlcam-stream.service is missing"
[[ -r "${mediamtx_unit}" ]] || fail "owlcam-mediamtx.service is missing"
[[ -r "${diagnostics_unit}" ]] || fail "owlcam-diagnostics.service is missing"

grep -F -- 'Restart=always' "${stream_unit}" >/dev/null \
  || fail "stream unit does not restart after a failure"
grep -F -- 'Restart=always' "${mediamtx_unit}" >/dev/null \
  || fail "mediamtx unit does not restart after a failure"
grep -F -- 'Restart=always' "${diagnostics_unit}" >/dev/null \
  || fail "diagnostics unit does not restart after a failure"
grep -F -- '127.0.0.1' "${REPO_ROOT}/pi/scripts/diagnostics_server.py" >/dev/null \
  || fail "diagnostics endpoint is not bound to loopback"
grep -F -- 'ProtectHome=read-only' "${diagnostics_unit}" >/dev/null \
  || fail "diagnostics unit can write to the user's home directory"
grep -F -- 'DeviceAllow=/dev/i2c-1 rw' "${diagnostics_unit}" >/dev/null \
  || fail "diagnostics unit cannot open the nest climate I2C bus"
# Capture published before MediaMTX is listening leaves the page on "resting".
grep -F -- 'After=owlcam-mediamtx.service' "${stream_unit}" >/dev/null \
  || fail "stream unit does not wait for the media server"
grep -F -- 'WantedBy=default.target' "${stream_unit}" >/dev/null \
  || fail "stream unit would not start at boot"
grep -F -- 'WantedBy=default.target' "${mediamtx_unit}" >/dev/null \
  || fail "mediamtx unit would not start at boot"

printf 'Script checks passed.\n'
