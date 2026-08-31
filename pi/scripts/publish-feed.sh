#!/usr/bin/env bash
set -euo pipefail

# Controls who can reach the OwlCam feed, without touching capture.
#
# Tailscale applies Serve and Funnel per *port*, not per mount point: whichever
# command ran last decides the exposure of everything on 443. The site, HLS,
# diagnostics, and admin mounts therefore have to be declared together in the
# same mode or changing exposure silently drops one. The admin API remains
# authenticated even when the port uses Funnel.

readonly HLS_PORT="${OWLCAM_HLS_PORT:-8888}"
readonly DIAGNOSTICS_PORT="${OWLCAM_DIAGNOSTICS_PORT:-8765}"
readonly ADMIN_PORT="${OWLCAM_ADMIN_PORT:-8766}"
readonly SITE_PORT="${OWLCAM_SITE_PORT:-8080}"
readonly STREAM_PATH="${OWLCAM_STREAM_PATH:-owl}"

mode=status

usage() {
  cat <<'EOF'
Usage: publish-feed.sh [--public | --private | --preserve | --status]

  --public    Publish over Tailscale Funnel. Anyone on the internet with the
              URL can watch, including phones that have never used Tailscale.
              The /diagnostics vitals become publicly readable too.
  --private   Publish over Tailscale Serve. Tailnet devices only.
  --preserve  Re-declare all mounts in whichever mode is already active,
              defaulting to private. Used by install-services.sh.
  --status    Show the current exposure and mounts (default).

Every mode declares all four mounts together: the page at /, the stream under
/owl, vitals at /diagnostics, and the authenticated API at /admin. The page and
stream must stay on one origin or browsers block video on Tailscale devices.

Optional environment:
  OWLCAM_HLS_PORT            MediaMTX HLS port, default 8888
  OWLCAM_DIAGNOSTICS_PORT    diagnostics port, default 8765
  OWLCAM_ADMIN_PORT          authenticated admin API port, default 8766
  OWLCAM_SITE_PORT           site server port, default 8080
  OWLCAM_STREAM_PATH         stream mount and MediaMTX path, default owl
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --public) mode=public ;;
    --private) mode=private ;;
    --preserve) mode=preserve ;;
    --status) mode=status ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

command -v tailscale >/dev/null 2>&1 || {
  printf 'Missing required command: tailscale\n' >&2
  exit 1
}

# AllowFunnel is the only authoritative signal; "tailscale funnel status" prints
# the same text as serve status and cannot be parsed apart from it.
current_exposure() {
  if tailscale serve status --json 2>/dev/null \
    | tr -d ' \n' \
    | grep -q '"AllowFunnel":{[^}]*:true'; then
    printf 'public\n'
  else
    printf 'private\n'
  fi
}

# Without the funnel node attribute, "tailscale funnel" blocks forever waiting on
# an approval that never arrives, and a killed attempt can leave the port with no
# mounts at all — which takes the feed down. Refuse before touching anything.
require_funnel_attribute() {
  if tailscale status --json \
    | tr -d ' \n' \
    | grep -q '"CapMap":{[^}]*funnel'; then
    return 0
  fi

  local node
  node="$(tailscale status --json \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["ID"])')"
  cat >&2 <<EOF
Refusing to publish: this node does not have the Tailscale funnel attribute.

Grant it once in the admin console, then re-run this script:
  https://login.tailscale.com/f/funnel?node=${node}

Until it is granted, "tailscale funnel" waits on approval indefinitely rather
than failing, so this script does not run it.
EOF
  exit 1
}

apply() {
  local verb="$1"

  # No pre-clear: Serve and Funnel share one mount table per port and the last
  # command wins, so re-declaring the mounts flips exposure in place. Clearing
  # first would drop the feed if the second command then failed.
  #
  # The page sits at the root and the stream moved under /<stream path>, so the
  # browser loads both from one origin. A page on a different origin cannot
  # reach a Tailscale address at all: MagicDNS resolves this host to a private
  # address on any device running Tailscale, and browsers refuse a public page
  # access to the local address space.
  #
  # --set-path strips its own prefix and appends the remainder to the target
  # URL's path, so /owl/index.m3u8 arrives at MediaMTX as /owl/index.m3u8 only
  # because the target repeats the path.
  tailscale "${verb}" --bg --yes --https=443 \
    "http://127.0.0.1:${SITE_PORT}"
  tailscale "${verb}" --bg --yes --https=443 --set-path="/${STREAM_PATH}" \
    "http://127.0.0.1:${HLS_PORT}/${STREAM_PATH}"
  tailscale "${verb}" --bg --yes --https=443 --set-path=/diagnostics \
    "http://127.0.0.1:${DIAGNOSTICS_PORT}"
  tailscale "${verb}" --bg --yes --https=443 --set-path=/admin \
    "http://127.0.0.1:${ADMIN_PORT}"
}

case "${mode}" in
  public)
    require_funnel_attribute
    apply funnel
    ;;
  private) apply serve ;;
  preserve)
    if [[ "$(current_exposure)" == public ]]; then
      apply funnel
    else
      apply serve
    fi
    ;;
esac

exposure="$(current_exposure)"
host="$(tailscale status --json | sed -n 's/.*"DNSName": *"\([^"]*\)\.".*/\1/p' | head -1)"

printf '\nExposure: %s\n' "${exposure}"
if [[ "${exposure}" == public ]]; then
  printf 'Anyone with the URL can watch. No sign-in, no tailnet needed.\n'
else
  printf 'Tailnet devices only. Sign in to Tailscale to watch.\n'
fi
printf 'Watch page: https://%s/\n' "${host}"
printf 'Stream URL: https://%s/%s/index.m3u8\n' "${host}" "${STREAM_PATH}"
printf 'Vitals URL: https://%s/diagnostics\n' "${host}"
printf 'Admin API: https://%s/admin/api/session\n' "${host}"
tailscale serve status 2>/dev/null || true
