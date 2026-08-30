#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
readonly TARGET="${OWLCAM_SSH_TARGET:-shawn@100.123.8.55}"
readonly REMOTE_STAGE="/home/shawn/owlcam/deploy"
readonly REMOTE_SITE="/home/shawn/owlcam/site"
readonly SITE_BUILD="${REPO_ROOT}/web/public"

dry_run=false
install_config=false

ssh_cmd=(ssh -o BatchMode=yes -o IdentitiesOnly=yes)
if [[ -n "${OWLCAM_SSH_IDENTITY:-}" ]]; then
  ssh_cmd+=(-i "${OWLCAM_SSH_IDENTITY}")
fi
rsync_excludes=(
  --exclude '*.secret'
  --exclude '*.key'
  --exclude '__pycache__'
  --exclude '*.pyc'
)

usage() {
  cat <<'EOF'
Usage: deploy.sh [--dry-run] [--install-config]

Stages OwlCam scripts and MediaMTX configuration over SSH. The live
configuration is replaced only when --install-config is explicitly supplied.

The built web site is staged too, because the Pi now serves the page beside the
stream so both share one origin. Run "make web-build" first; an unbuilt site is
reported rather than silently skipped.

Optional environment:
  OWLCAM_SSH_TARGET     default shawn@100.123.8.55
  OWLCAM_SSH_IDENTITY   path to a private key for BatchMode SSH
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=true ;;
    --install-config) install_config=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

if "${dry_run}"; then
  printf 'Would stage %s/pi/scripts/ at %s:%s/pi/scripts/\n' \
    "${REPO_ROOT}" "${TARGET}" "${REMOTE_STAGE}"
  printf 'Would stage %s/pi/config/ at %s:%s/pi/config/\n' \
    "${REPO_ROOT}" "${TARGET}" "${REMOTE_STAGE}"
  printf 'Would stage %s/pi/systemd/ at %s:%s/pi/systemd/\n' \
    "${REPO_ROOT}" "${TARGET}" "${REMOTE_STAGE}"
  printf 'Would stage %s/scripts/ at %s:%s/scripts/\n' \
    "${REPO_ROOT}" "${TARGET}" "${REMOTE_STAGE}"
  printf 'Would stage %s/ at %s:%s/ (deleting removed files)\n' \
    "${SITE_BUILD}" "${TARGET}" "${REMOTE_SITE}"
  if "${install_config}"; then
    printf 'Would back up and install mediamtx.yml as /etc/mediamtx.yml\n'
  fi
  exit 0
fi

if "${install_config}" && [[ ! -r "${REPO_ROOT}/pi/config/mediamtx.yml" ]]; then
  printf 'Refusing configuration install: pi/config/mediamtx.yml is missing.\n' >&2
  exit 1
fi

"${ssh_cmd[@]}" "${TARGET}" \
  "mkdir -p '${REMOTE_STAGE}/pi/scripts' '${REMOTE_STAGE}/pi/config' '${REMOTE_STAGE}/pi/systemd' '${REMOTE_STAGE}/scripts'"
rsync -av "${rsync_excludes[@]}" \
  -e "${ssh_cmd[*]}" \
  "${REPO_ROOT}/pi/scripts/" "${TARGET}:${REMOTE_STAGE}/pi/scripts/"
rsync -av "${rsync_excludes[@]}" \
  -e "${ssh_cmd[*]}" \
  "${REPO_ROOT}/pi/config/" "${TARGET}:${REMOTE_STAGE}/pi/config/"
rsync -av "${rsync_excludes[@]}" \
  -e "${ssh_cmd[*]}" \
  "${REPO_ROOT}/pi/systemd/" "${TARGET}:${REMOTE_STAGE}/pi/systemd/"
rsync -av "${rsync_excludes[@]}" \
  -e "${ssh_cmd[*]}" \
  "${REPO_ROOT}/scripts/" "${TARGET}:${REMOTE_STAGE}/scripts/"

if [[ -f "${SITE_BUILD}/index.html" ]]; then
  "${ssh_cmd[@]}" "${TARGET}" "mkdir -p '${REMOTE_SITE}'"
  # --delete is required, not tidiness: every build fingerprints CSS and JS
  # under a new name, so without it the old copies pile up on the SD card forever.
  rsync -av --delete "${rsync_excludes[@]}" \
    -e "${ssh_cmd[*]}" \
    "${SITE_BUILD}/" "${TARGET}:${REMOTE_SITE}/"
else
  printf 'Site not staged: %s/index.html is missing. Run "make web-build".\n' \
    "${SITE_BUILD}" >&2
fi

if "${install_config}"; then
  "${ssh_cmd[@]}" "${TARGET}" \
    'backup="/etc/mediamtx.yml.bak.$(date -u +%Y%m%dT%H%M%SZ)"; sudo cp /etc/mediamtx.yml "${backup}" && sudo install -m 0644 /home/shawn/owlcam/deploy/pi/config/mediamtx.yml /etc/mediamtx.yml && printf "Backup: %s\n" "${backup}"'
fi

printf 'OwlCam files staged on %s.\n' "${TARGET}"
