#!/usr/bin/env bash
# Enable I2S capture for the INMP441 on Raspberry Pi OS.
# Run on the Pi: sudo ./pi/scripts/configure-i2s-mic.sh
# Prints the config.txt diff. Pass --reboot to reboot after a successful edit.
set -euo pipefail

reboot_after=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reboot) reboot_after=true ;;
    -h|--help)
      printf 'Usage: sudo %s [--reboot]\n' "$0"
      printf 'Enables dtparam=i2s=on and dtoverlay=googlevoicehat-soundcard\n'
      printf 'in /boot/firmware/config.txt (or /boot/config.txt).\n'
      exit 0
      ;;
    *)
      printf 'unknown option: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "${EUID}" -ne 0 ]]; then
  printf 'Run as root: sudo %s\n' "$0" >&2
  exit 1
fi

config=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
  if [[ -f "${candidate}" ]]; then
    config="${candidate}"
    break
  fi
done
if [[ -z "${config}" ]]; then
  printf 'No Raspberry Pi boot config found.\n' >&2
  exit 1
fi

stamp="$(date -u +%Y%m%d_%H%M%S)"
backup="${config}.backup.${stamp}"
cp -a "${config}" "${backup}"
printf 'Backup: %s\n' "${backup}"

python3 - "${config}" << 'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1])
text = src.read_text()
original = text
lines = text.splitlines(keepends=True)
new_lines = []
i2s_enabled = False
for line in lines:
    if line.strip().lstrip("#").strip() == "dtparam=i2s=on":
        new_lines.append("dtparam=i2s=on\n")
        i2s_enabled = True
    else:
        new_lines.append(line)

if not i2s_enabled:
    rebuilt = []
    inserted = False
    for line in new_lines:
        rebuilt.append(line)
        if (not inserted) and line.strip().startswith("dtparam=i2c_arm=on"):
            rebuilt.append("dtparam=i2s=on\n")
            inserted = True
            i2s_enabled = True
    new_lines = rebuilt

text = "".join(new_lines)
if not any(
    (not line.lstrip().startswith("#")) and line.strip() == "dtparam=i2s=on"
    for line in text.splitlines()
):
    if not text.endswith("\n"):
        text += "\n"
    text += "dtparam=i2s=on\n"

overlay_present = any(
    (not line.lstrip().startswith("#")) and "dtoverlay=googlevoicehat-soundcard" in line
    for line in text.splitlines()
)
if not overlay_present:
    needle = "[all]\n"
    overlay_line = "dtoverlay=googlevoicehat-soundcard\n"
    if needle in text:
        text = text.replace(needle, needle + overlay_line, 1)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += overlay_line

src.write_text(text)
print("CHANGED" if text != original else "UNCHANGED")
PY

if command -v diff >/dev/null 2>&1; then
  diff -u "${backup}" "${config}" || true
fi

printf 'I2S overlay googlevoicehat-soundcard is configured in %s\n' "${config}"
printf 'dtparam=audio=on was left in place. Disable it only if I2S fails to bind.\n'

if "${reboot_after}"; then
  printf 'Rebooting...\n'
  reboot
fi
