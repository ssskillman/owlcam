#!/usr/bin/env bash
# End-to-end: admin login, delete a nest visit, confirm suppression list updates.
#
# From a workstation (hits the public Tailscale URL):
#   OWLCAM_E2E_ADMIN_USER=ccarver OWLCAM_E2E_ADMIN_PASSWORD='…' \
#     ANIMAL_ID_API_ORIGIN=https://penns-gaming-pc.tail31318f.ts.net:8443 \
#     ./pi/scripts/e2e-nest-visit-delete.sh
#
# On the Pi (loopback admin, same URL for site if funnel is up):
#   OWLCAM_SITE_URL=https://owlcam.tail31318f.ts.net \
#     OWLCAM_E2E_ADMIN_USER=… OWLCAM_E2E_ADMIN_PASSWORD=… \
#     ./pi/scripts/e2e-nest-visit-delete.sh
set -euo pipefail

readonly SITE_URL="${OWLCAM_SITE_URL:-https://owlcam.tail31318f.ts.net}"
readonly API_ORIGIN="${ANIMAL_ID_API_ORIGIN:-}"
readonly ADMIN_USER="${OWLCAM_E2E_ADMIN_USER:-}"
readonly ADMIN_PASSWORD="${OWLCAM_E2E_ADMIN_PASSWORD:-}"
readonly COOKIE_JAR="$(mktemp)"
readonly VISIT_ID="${OWLCAM_E2E_VISIT_ID:-}"

cleanup() {
  rm -f "${COOKIE_JAR}"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

pass() {
  printf 'PASS: %s\n' "$1"
}

if [[ -z "${ADMIN_USER}" || -z "${ADMIN_PASSWORD}" ]]; then
  fail "set OWLCAM_E2E_ADMIN_USER and OWLCAM_E2E_ADMIN_PASSWORD"
fi

if [[ -z "${API_ORIGIN}" ]]; then
  fail "set ANIMAL_ID_API_ORIGIN (inference host origin, no trailing slash)"
fi

printf '=== OwlCam nest visit delete E2E ===\n'
printf 'Site: %s\n' "${SITE_URL}"

login_body="$(mktemp)"
login_json="$(
  python3 -c 'import json, sys; print(json.dumps({"username": sys.argv[1], "password": sys.argv[2]}))' \
    "${ADMIN_USER}" "${ADMIN_PASSWORD}"
)"
login_status="$(
  curl -sS -m 30 -o "${login_body}" -w '%{http_code}' \
    -c "${COOKIE_JAR}" \
    -H 'Content-Type: application/json' \
    -H "Origin: ${SITE_URL}" \
    -X POST "${SITE_URL}/admin/api/session" \
    -d "${login_json}"
)"
if [[ "${login_status}" != "200" ]]; then
  cat "${login_body}" >&2 || true
  rm -f "${login_body}"
  fail "admin login returned HTTP ${login_status}"
fi
csrf="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["csrfToken"])' <"${login_body}")"
rm -f "${login_body}"
if [[ -z "${csrf}" ]]; then
  fail "login response missing csrfToken"
fi
pass "admin login"

if [[ -n "${VISIT_ID}" ]]; then
  target_id="${VISIT_ID}"
else
  visits_json="$(curl -sS -m 30 "${API_ORIGIN}/api/animal-identification/visits?limit=5")"
  target_id="$(
    printf '%s' "${visits_json}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
visits = data.get("visits") or []
if not visits:
    raise SystemExit("no visits in feed")
print(visits[0]["id"])
'
  )"
fi
printf 'Target visit id: %s\n' "${target_id}"

delete_body="$(mktemp)"
delete_status="$(
  curl -sS -m 30 -o "${delete_body}" -w '%{http_code}' \
    -b "${COOKIE_JAR}" \
    -H "X-Owlcam-Csrf: ${csrf}" \
    -H "Origin: ${SITE_URL}" \
    -X DELETE "${SITE_URL}/admin/api/nest-visits/${target_id}"
)"
if [[ "${delete_status}" != "200" ]]; then
  if [[ -s "${delete_body}" ]]; then
    cat "${delete_body}" >&2
  else
    printf '(empty response body — admin API may have crashed; try: ssh pi systemctl --user restart owlcam-admin)\n' >&2
  fi
  rm -f "${delete_body}"
  fail "DELETE nest visit returned HTTP ${delete_status}"
fi
mode="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("mode",""))' <"${delete_body}")"
rm -f "${delete_body}"
if [[ "${mode}" != "remote" && "${mode}" != "suppressed" ]]; then
  fail "unexpected delete mode: ${mode}"
fi
pass "DELETE /admin/api/nest-visits/${target_id} (mode=${mode})"

suppressed_json="$(curl -sS -m 15 "${SITE_URL}/api/nest-visits-suppressed")"
python3 -c '
import json, sys
target = int(sys.argv[1])
data = json.load(sys.stdin)
ids = set(data.get("visitIds") or [])
if target not in ids:
    raise SystemExit(f"visit {target} not in suppressed list: {sorted(ids)}")
print("ok")
' "${target_id}" <<<"${suppressed_json}"
pass "suppressed list includes visit ${target_id}"

printf '\nNest visit delete E2E complete.\n'
