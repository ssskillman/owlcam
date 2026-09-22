#!/usr/bin/env bash
# Phase 0 — automated checks for live HLS and local services.
# Run on the Pi: ./pi/scripts/e2e-phase0-feed.sh
# Phone steps (0.5–0.6) remain manual; this script prints reminders.
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly HLS_PORT="${OWLCAM_HLS_PORT:-8888}"
readonly STREAM_PATH="${OWLCAM_STREAM_PATH:-owl}"
readonly HLS_URL="http://127.0.0.1:${HLS_PORT}/${STREAM_PATH}/index.m3u8"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

pass() {
  printf 'PASS: %s\n' "$1"
}

media_playlist_url() {
  local master_url="$1"
  local body variant line
  body="$(curl -fsSL -m 5 "${master_url}")"
  if printf '%s' "${body}" | grep -q '^#EXT-X-MEDIA-SEQUENCE:'; then
    printf '%s' "${master_url}"
    return 0
  fi
  variant="$(printf '%s' "${body}" | awk '!/^#/ && NF {print $1; exit}')"
  if [[ -z "${variant}" ]]; then
    fail "could not resolve HLS media playlist from master"
  fi
  if [[ "${variant}" == http://* || "${variant}" == https://* ]]; then
    printf '%s' "${variant}"
  else
    local base="${master_url%/*}"
    printf '%s/%s' "${base}" "${variant}"
  fi
}

printf '=== OwlCam Phase 0 feed E2E (automated) ===\n\n'

for unit in owlcam-mediamtx owlcam-stream owlcam-site; do
  state="$(systemctl --user is-active "${unit}.service" 2>/dev/null || true)"
  if [[ "${state}" != "active" ]]; then
    fail "${unit} is not active (got ${state:-missing})"
  fi
  pass "${unit} is active"
done

code="$(curl -L -sS -o /dev/null -w '%{http_code}' -m 5 "${HLS_URL}")"
if [[ "${code}" != "200" ]]; then
  fail "HLS playlist HTTP ${code} (expected 200 with -L for cookieCheck)"
fi
pass "HLS playlist returns HTTP 200"

MEDIA_URL="$(media_playlist_url "${HLS_URL}")"
playlist="$(curl -fsSL -m 5 "${MEDIA_URL}")"
seq1="$(printf '%s' "${playlist}" | awk -F: '/^#EXT-X-MEDIA-SEQUENCE:/ {gsub(/\r/,"",$2); print $2; exit}')"
if [[ -z "${seq1}" ]]; then
  fail "media playlist missing #EXT-X-MEDIA-SEQUENCE"
fi
sleep 10
playlist2="$(curl -fsSL -m 5 "${MEDIA_URL}")"
seq2="$(printf '%s' "${playlist2}" | awk -F: '/^#EXT-X-MEDIA-SEQUENCE:/ {gsub(/\r/,"",$2); print $2; exit}')"
if [[ -z "${seq2}" ]]; then
  fail "second playlist missing media sequence"
fi
if [[ "${seq2}" -le "${seq1}" ]]; then
  fail "media sequence did not advance (${seq1} -> ${seq2})"
fi
pass "HLS media sequence advanced (${seq1} -> ${seq2})"

if [[ -x "${SCRIPT_DIR}/publish-feed.sh" ]]; then
  "${SCRIPT_DIR}/publish-feed.sh" --status || true
  pass "publish-feed.sh --status ran (verify mounts include /, /owl, /diagnostics, /admin)"
else
  printf 'SKIP: publish-feed.sh not found\n'
fi

printf '\nManual (not automated here):\n'
printf '  - Phone without Tailscale: https://carver-owlcam-72343.web.app — video + diagnostics\n'
printf '  - Phone with Tailscale: same origin, no private-IP block\n'
printf '  - Admin: nest stream toggle off/on; USB stream must survive if enabled\n'
printf '\nPhase 0 automated checks complete.\n'
