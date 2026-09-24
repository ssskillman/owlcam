#!/usr/bin/env bash
# Record a test WAV from the OwlCam I2S microphone and print PASS/FAIL.
# Run on the Pi. Does not delete recordings.
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
duration=10
device="${OWLCAM_ALSA_DEVICE:-owlmic}"
out_dir="${OWLCAM_AUDIO_TEST_DIR:-${HOME}/owlcam/audio_tests}"

usage() {
  cat <<EOF
Usage: $0 [--duration SECONDS] [--device ALSA_DEVICE]

Records a mono 48 kHz S32_LE WAV, prints sox/python stats, and exits
nonzero if the file is missing, silent, or clipped.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --duration)
      duration="${2:?}"
      shift 2
      ;;
    --device)
      device="${2:?}"
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

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

pass() {
  printf 'PASS: %s\n' "$1"
}

command -v arecord >/dev/null 2>&1 || fail "arecord is not installed"
if [[ "${duration}" -lt 1 ]]; then
  fail "duration must be at least 1"
fi

if ! arecord -L 2>/dev/null | grep -qx "${device}" \
  && ! arecord -L 2>/dev/null | grep -q "^${device}$" \
  && ! arecord -L 2>/dev/null | grep -q "${device}"; then
  # Named pcms from ~/.asoundrc may not appear in arecord -L until the file
  # exists. Still try hw:CARD names that are listed.
  if ! arecord -l 2>/dev/null | grep -qiE 'voicehat|googlevoice|sndrpigoogle'; then
    arecord -l >&2 || true
    fail "no I2S capture device found (looked for ${device})"
  fi
fi

mkdir -p "${out_dir}"
stamp="$(date +%Y%m%d_%H%M%S)"
wav="${out_dir}/mic_test_${stamp}.wav"

python3 "${SCRIPT_DIR}/capture_audio.py" \
  --duration "${duration}" \
  --device "${device}" \
  --output "${wav}" || fail "capture failed"

[[ -f "${wav}" ]] || fail "WAV was not created"

if command -v sox >/dev/null 2>&1; then
  sox "${wav}" -n stats || true
fi

stats="$(python3 - "${SCRIPT_DIR}/capture_audio.py" "${wav}" << 'PY'
import importlib.util
import json
import sys
from pathlib import Path

module_path = Path(sys.argv[1])
wav_path = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("owlcam_capture_audio", module_path)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)
print(json.dumps(mod.wav_stats(wav_path)))
PY
)"

python3 - "${stats}" "${wav}" << 'PY' || fail "audio quality check failed"
import json
import sys
from pathlib import Path

stats = json.loads(sys.argv[1])
wav = Path(sys.argv[2])
print(
    "frames={frames} rate={rate} peak={peak} rms={rms:.1f} all_zero={all_zero} clipped={clipped}".format(
        **{**stats, "rms": float(stats["rms"])}
    )
)
print(f"file={wav} bytes={wav.stat().st_size}")
if stats["all_zero"]:
    raise SystemExit("recording is silence")
if stats["clipped"]:
    raise SystemExit("recording is constantly full-scale")
if stats["frames"] < 1:
    raise SystemExit("recording has no frames")
PY

pass "recorded ${wav}"
