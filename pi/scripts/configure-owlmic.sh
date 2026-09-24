#!/usr/bin/env bash
# Write ~/.asoundrc so arecord -D owlmic uses the INMP441 I2S card by name.
#
# The alias is a dsnoop device, not the raw card: an ALSA capture device can
# only be opened once, and both camera publishes plus a manual test recording
# need the same microphone at the same time.
set -euo pipefail

asoundrc="${HOME}/.asoundrc"
card_name=""

usage() {
  cat <<EOF
Usage: $0 [--card CARDNAME]

CARDNAME defaults to the first ALSA capture card matching voicehat/googlevoice.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --card)
      card_name="${2:?}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${card_name}" ]]; then
  card_name="$(arecord -l 2>/dev/null | awk '
    /card [0-9]+:/ && tolower($0) ~ /voicehat|googlevoice|sndrpigoogle/ {
      split($0, left, ": ")
      split(left[2], name, " ")
      print name[1]
      exit
    }')"
fi

if [[ -z "${card_name}" ]]; then
  printf 'No Google voiceHAT / I2S capture card found. Run arecord -l after the overlay is loaded.\n' >&2
  arecord -l >&2 || true
  exit 1
fi

if [[ -f "${asoundrc}" ]]; then
  cp -a "${asoundrc}" "${asoundrc}.bak.$(date +%Y%m%d_%H%M%S)"
fi

CARD_NAME="${card_name}" ASOUNDRC="${asoundrc}" python3 - <<'PY'
import os
from pathlib import Path

card = os.environ["CARD_NAME"]
path = Path(os.environ["ASOUNDRC"])
start = "# >>> owlcam owlmic >>>"
end = "# <<< owlcam owlmic <<<"

block = f"""{start}
# OwlCam INMP441 I2S capture. Card name, not a numeric index: the number
# moves when the USB camera enumerates.
pcm.owlmic_dsnoop {{
    type dsnoop
    ipc_key 2748
    ipc_perm 0666
    slave {{
        pcm "hw:{card},0"
        channels 2
        rate 48000
        format S32_LE
        period_size 1024
        buffer_size 8192
    }}
}}

# L/R is strapped to GND, so the microphone sits in the left slot only.
pcm.owlmic {{
    type plug
    slave.pcm "owlmic_dsnoop"
    ttable.0.0 1
    ttable.0.1 0
}}

ctl.owlmic {{
    type hw
    card "{card}"
}}
{end}
"""

text = path.read_text() if path.exists() else ""
if start in text and end in text:
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    text = head + block + tail.lstrip("\n")
else:
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n" + block

path.write_text(text)
PY

printf 'owlmic -> dsnoop over hw:%s,0 in %s\n' "${card_name}" "${asoundrc}"
arecord -L | grep -E '^owlmic$' || true
