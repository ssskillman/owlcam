#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
readonly VERSION_FILE="${REPO_ROOT}/pi/config/mediamtx.version"

usage() {
  printf 'Usage: %s [--check]\n' "$0"
}

if [[ ! -r "${VERSION_FILE}" ]]; then
  printf 'Missing version pin: %s\n' "${VERSION_FILE}" >&2
  exit 1
fi

MEDIAMTX_VERSION="$(tr -d '\r\n' < "${VERSION_FILE}")"
if [[ ! "${MEDIAMTX_VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Invalid MediaMTX version pin: %s\n' "${MEDIAMTX_VERSION}" >&2
  exit 1
fi
readonly MEDIAMTX_VERSION
readonly MEDIAMTX_ARCHIVE="mediamtx_${MEDIAMTX_VERSION}_linux_arm64.tar.gz"

if [[ "${1:-}" == "--check" ]]; then
  command -v rpicam-vid
  command -v ffmpeg
  command -v mediamtx
  installed_version="$(mediamtx --version)"
  printf 'MediaMTX installed=%s pinned=%s\n' \
    "${installed_version}" "${MEDIAMTX_VERSION}"
  [[ "${installed_version}" == "${MEDIAMTX_VERSION}" ]]
  exit 0
elif [[ $# -ne 0 ]]; then
  usage >&2
  exit 2
fi

if [[ "$(uname -m)" != "aarch64" ]]; then
  printf 'This installer supports only aarch64 Raspberry Pi OS.\n' >&2
  exit 1
fi

readonly RELEASE_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}"
work_dir="$(mktemp -d)"
trap 'rm -rf -- "${work_dir}"' EXIT

sudo apt-get update
sudo apt-get install -y ca-certificates curl ffmpeg rpicam-apps

curl --fail --location --proto '=https' --tlsv1.2 \
  --connect-timeout 15 --max-time 300 --retry 3 --retry-all-errors \
  --output "${work_dir}/${MEDIAMTX_ARCHIVE}" \
  "${RELEASE_URL}/${MEDIAMTX_ARCHIVE}"
curl --fail --location --proto '=https' --tlsv1.2 \
  --connect-timeout 15 --max-time 60 --retry 3 --retry-all-errors \
  --output "${work_dir}/checksums.sha256" \
  "${RELEASE_URL}/checksums.sha256"

(
  cd "${work_dir}"
  awk -v archive="${MEDIAMTX_ARCHIVE}" '$2 == archive { print }' checksums.sha256 \
    > expected.sha256
  [[ -s expected.sha256 ]]
  sha256sum --check expected.sha256
  tar -xzf "${MEDIAMTX_ARCHIVE}" mediamtx
)

sudo install -m 0755 "${work_dir}/mediamtx" /usr/local/bin/mediamtx
printf 'Installed MediaMTX %s.\n' "${MEDIAMTX_VERSION}"
