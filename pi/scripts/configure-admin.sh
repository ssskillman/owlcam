#!/usr/bin/env bash
set -euo pipefail

# Creates the local-only credential file consumed by owlcam-admin.service.
# Password input is never echoed, written to shell history, or stored as text.
umask 077

readonly CONFIG_DIR="${HOME}/.config/owlcam"
readonly CONFIG_FILE="${CONFIG_DIR}/admin.env"

[[ -t 0 ]] || {
  printf 'Run this script from an interactive terminal.\n' >&2
  exit 1
}

read -rp 'Admin username [admin]: ' username
username="${username:-admin}"
if [[ ! "${username}" =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
  printf 'Username may contain only letters, numbers, dot, underscore, and dash.\n' >&2
  exit 2
fi

read -rsp 'Admin password (16+ characters): ' password
printf '\n'
read -rsp 'Confirm admin password: ' confirmation
printf '\n'

if [[ "${password}" != "${confirmation}" ]]; then
  printf 'Passwords do not match.\n' >&2
  exit 2
fi
if (( ${#password} < 16 )); then
  printf 'Password must be at least 16 characters.\n' >&2
  exit 2
fi

password_hash="$(
  python3 -c '
import base64, hashlib, secrets, sys
password = sys.stdin.buffer.readline().rstrip(b"\n")
salt = secrets.token_bytes(16)
digest = hashlib.scrypt(password, salt=salt, n=2**14, r=8, p=1, dklen=32)
encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
print(f"scrypt:16384:8:1:{encode(salt)}:{encode(digest)}")
' <<<"${password}"
)"
unset password confirmation

mkdir -p "${CONFIG_DIR}"
temporary="$(mktemp "${CONFIG_DIR}/admin.env.XXXXXX")"
{
  printf 'OWLCAM_ADMIN_USERNAME=%s\n' "${username}"
  printf 'OWLCAM_ADMIN_PASSWORD_HASH=%s\n' "${password_hash}"
} > "${temporary}"
chmod 600 "${temporary}"
mv "${temporary}" "${CONFIG_FILE}"

printf 'Admin credentials written to %s (mode 600).\n' "${CONFIG_FILE}"
if systemctl --user --quiet is-enabled owlcam-admin.service 2>/dev/null; then
  systemctl --user restart owlcam-admin.service
  printf 'owlcam-admin.service restarted. Existing sessions were signed out.\n'
else
  printf 'Install the OwlCam services to activate the admin API.\n'
fi
