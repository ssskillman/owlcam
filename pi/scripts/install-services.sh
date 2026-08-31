#!/usr/bin/env bash
set -euo pipefail

# Installs the OwlCam capture and MediaMTX units so the feed comes back by
# itself after a reboot or a crash.
#
# These are *user* units, not system units. The Pi has no passwordless sudo, and
# user units plus lingering achieve the same result: start at boot, restart on
# failure, no password prompt during install.

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly UNIT_SRC="${SCRIPT_DIR}/../systemd"
readonly UNIT_DIR="${HOME}/.config/systemd/user"
readonly BIN_DIR="${HOME}/.local/bin"

uninstall=false

usage() {
  cat <<'EOF'
Usage: install-services.sh [--uninstall]

  (default)    Install and start media, stream, site, diagnostics, and admin.
  --uninstall  Stop, disable, and remove all five units.

The site unit serves the built page from ${HOME}/owlcam/site, which deploy.sh
stages. Build and stage it before installing, or the page will 404.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall) uninstall=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

require() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

require systemctl
require loginctl

if "${uninstall}"; then
  # A mount could have been declared in either mode, and clearing one does
  # not clear the other.
  for mount_path in /admin /diagnostics "/${OWLCAM_STREAM_PATH:-owl}"; do
    tailscale funnel --https=443 --set-path="${mount_path}" off 2>/dev/null || true
    tailscale serve --https=443 --set-path="${mount_path}" off 2>/dev/null || true
  done
  tailscale funnel --https=443 off 2>/dev/null || true
  tailscale serve --https=443 off 2>/dev/null || true
  systemctl --user disable --now owlcam-admin.service 2>/dev/null || true
  systemctl --user disable --now owlcam-diagnostics.service 2>/dev/null || true
  systemctl --user disable --now owlcam-site.service 2>/dev/null || true
  systemctl --user disable --now owlcam-stream.service 2>/dev/null || true
  systemctl --user disable --now owlcam-mediamtx.service 2>/dev/null || true
  rm -f "${UNIT_DIR}/owlcam-diagnostics.service" \
        "${UNIT_DIR}/owlcam-admin.service" \
        "${UNIT_DIR}/owlcam-site.service" \
        "${UNIT_DIR}/owlcam-stream.service" \
        "${UNIT_DIR}/owlcam-mediamtx.service" \
        "${BIN_DIR}/owlcam-diagnostics" \
        "${BIN_DIR}/owlcam-admin" \
        "${BIN_DIR}/owlcam-configure-admin" \
        "${BIN_DIR}/owlcam-site" \
        "${BIN_DIR}/owlcam-start-stream"
  systemctl --user daemon-reload
  printf 'OwlCam services removed.\n'
  exit 0
fi

require mediamtx
require rpicam-vid
require ffmpeg
require python3
require tailscale

# Without lingering, user units stop when the last SSH session closes and never
# start at boot, which is the entire point of installing them.
loginctl enable-linger "${USER}"

mkdir -p "${UNIT_DIR}" "${BIN_DIR}"
install -m 0755 "${SCRIPT_DIR}/start-stream.sh" "${BIN_DIR}/owlcam-start-stream"
install -m 0755 "${SCRIPT_DIR}/diagnostics_server.py" "${BIN_DIR}/owlcam-diagnostics"
install -m 0755 "${SCRIPT_DIR}/admin_server.py" "${BIN_DIR}/owlcam-admin"
install -m 0755 "${SCRIPT_DIR}/configure-admin.sh" "${BIN_DIR}/owlcam-configure-admin"
install -m 0755 "${SCRIPT_DIR}/site_server.py" "${BIN_DIR}/owlcam-site"
install -m 0644 "${UNIT_SRC}/owlcam-diagnostics.service" "${UNIT_DIR}/"
install -m 0644 "${UNIT_SRC}/owlcam-admin.service" "${UNIT_DIR}/"
install -m 0644 "${UNIT_SRC}/owlcam-mediamtx.service" "${UNIT_DIR}/"
install -m 0644 "${UNIT_SRC}/owlcam-site.service" "${UNIT_DIR}/"
install -m 0644 "${UNIT_SRC}/owlcam-stream.service" "${UNIT_DIR}/"

# A capture started by hand, or by the UDP script, holds the sensor and would
# make the new unit fail on every restart attempt.
if pgrep -x rpicam-vid >/dev/null 2>&1; then
  printf 'Stopping an existing camera capture so the unit can claim the sensor.\n'
  pkill -x rpicam-vid 2>/dev/null || true
  sleep 2
  pkill -x ffmpeg 2>/dev/null || true
  sleep 1
fi

# MediaMTX started by hand would keep port 8888 and the unit would restart forever.
if pgrep -x mediamtx >/dev/null 2>&1; then
  printf 'Stopping a hand-started MediaMTX so the unit owns the port.\n'
  pkill -x mediamtx 2>/dev/null || true
  sleep 2
fi

systemctl --user daemon-reload
systemctl --user enable owlcam-mediamtx.service
systemctl --user enable owlcam-stream.service
systemctl --user enable owlcam-site.service
systemctl --user enable owlcam-diagnostics.service
systemctl --user enable owlcam-admin.service

# Restart rather than "enable --now": an already-running unit keeps executing the
# binary it started with, so freshly staged code would not take effect until the
# next reboot.
systemctl --user restart owlcam-mediamtx.service
sleep 3
systemctl --user restart owlcam-stream.service
systemctl --user restart owlcam-site.service
systemctl --user restart owlcam-diagnostics.service
systemctl --user restart owlcam-admin.service

printf '\nWaiting for local HLS...\n'
hls_url="http://127.0.0.1:${OWLCAM_HLS_PORT:-8888}/${OWLCAM_STREAM_PATH:-owl}/index.m3u8"
for _ in $(seq 1 20); do
  # MediaMTX answers the first request with a 302 to ?cookieCheck=1, so a bare
  # request without redirect following reports a false failure.
  if curl -fsSL -m 3 -o /dev/null "${hls_url}"; then
    ready=true
    break
  fi
  sleep 2
done

if [[ "${ready:-false}" != true ]]; then
  printf 'Local HLS never became ready. Check:\n' >&2
  printf '  systemctl --user status owlcam-stream owlcam-mediamtx\n' >&2
  printf '  journalctl --user -u owlcam-stream -n 50\n' >&2
  exit 1
fi

printf '\nWaiting for local diagnostics...\n'
diagnostics_url="http://127.0.0.1:${OWLCAM_DIAGNOSTICS_PORT:-8765}/diagnostics"
for _ in $(seq 1 10); do
  if curl -fsS -m 3 -o /dev/null "${diagnostics_url}"; then
    diagnostics_ready=true
    break
  fi
  sleep 1
done

if [[ "${diagnostics_ready:-false}" != true ]]; then
  printf 'Local diagnostics never became ready. Check:\n' >&2
  printf '  systemctl --user status owlcam-diagnostics\n' >&2
  exit 1
fi

printf '\nWaiting for the local site...\n'
site_url="http://127.0.0.1:${OWLCAM_SITE_PORT:-8080}/"
for _ in $(seq 1 10); do
  if curl -fsS -m 3 -o /dev/null "${site_url}"; then
    site_ready=true
    break
  fi
  sleep 1
done

# A running server with no files answers 404, which looks like a healthy unit
# but serves a blank site, so the check asks for the page itself.
if [[ "${site_ready:-false}" != true ]]; then
  printf 'The local site never answered. Check:\n' >&2
  printf '  systemctl --user status owlcam-site\n' >&2
  printf '  ls %s/owlcam/site/index.html\n' "${HOME}" >&2
  printf 'If the site directory is empty, build and stage it first:\n' >&2
  printf '  make web-build && bash pi/scripts/deploy.sh   (from a workstation)\n' >&2
  exit 1
fi

printf '\nWaiting for the local admin API...\n'
admin_url="http://127.0.0.1:${OWLCAM_ADMIN_PORT:-8766}/api/session"
for _ in $(seq 1 10); do
  if curl -fsS -m 3 -o /dev/null "${admin_url}"; then
    admin_ready=true
    break
  fi
  sleep 1
done

if [[ "${admin_ready:-false}" != true ]]; then
  printf 'The local admin API never answered. Check:\n' >&2
  printf '  systemctl --user status owlcam-admin\n' >&2
  exit 1
fi

# Declares the HLS root and the diagnostics mount together, keeping whatever
# exposure is already in effect so a reinstall cannot pull a deliberately public
# feed back to tailnet-only. Tailscale persists this across reboots.
"${SCRIPT_DIR}/publish-feed.sh" --preserve

printf 'OwlCam services installed and serving.\n'
systemctl --user is-enabled \
  owlcam-mediamtx.service \
  owlcam-stream.service \
  owlcam-site.service \
  owlcam-diagnostics.service \
  owlcam-admin.service
