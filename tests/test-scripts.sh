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
grep -F -- "-c:v copy" "${stream_script}" >/dev/null \
  || fail "stream script would re-encode video"
grep -F -- "-fflags +genpts" "${stream_script}" >/dev/null \
  || fail "stream script is missing generated timestamps"
grep -F -- "rtsp://127.0.0.1:8554/owl" "${stream_script}" >/dev/null \
  || fail "stream script default RTSP path changed"

printf 'Script checks passed.\n'
