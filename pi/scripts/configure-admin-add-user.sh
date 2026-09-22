#!/usr/bin/env bash
set -euo pipefail

# Append an additional admin user to ~/.config/owlcam/admin-users without
# replacing the primary credentials in admin.env.
umask 077

readonly CONFIG_DIR="${HOME}/.config/owlcam"
readonly USERS_FILE="${CONFIG_DIR}/admin-users"

[[ -t 0 ]] || {
  printf 'Run this script from an interactive terminal.\n' >&2
  exit 1
}

read -rp 'Additional admin username: ' username
if [[ ! "${username}" =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
  printf 'Username may contain only letters, numbers, dot, underscore, and dash.\n' >&2
  exit 2
fi

if [[ -f "${USERS_FILE}" ]] && grep -q "^${username}:" "${USERS_FILE}"; then
  printf 'That username already exists in %s.\n' "${USERS_FILE}" >&2
  exit 2
fi

read -rsp 'Password (16+ characters): ' password
printf '\n'
read -rsp 'Confirm password: ' confirmation
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
printf '%s:%s\n' "${username}" "${password_hash}" >> "${USERS_FILE}"
chmod 600 "${USERS_FILE}"

printf 'Added %s to %s (mode 600).\n' "${username}" "${USERS_FILE}"
if systemctl --user --quiet is-enabled owlcam-admin.service 2>/dev/null; then
  systemctl --user restart owlcam-admin.service
  printf 'owlcam-admin.service restarted. Existing sessions were signed out.\n'
fi
