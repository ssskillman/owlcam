#!/usr/bin/env python3
"""Record a mono WAV from the OwlCam I2S microphone via arecord."""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

DEFAULT_DEVICE = "owlmic"
SAMPLE_RATE = 48000
CHANNELS = 1
SAMPLE_FORMAT = "S32_LE"
SAMPLE_WIDTH = 4


def wav_stats(path: Path) -> dict[str, float | int | bool]:
    """Return peak/RMS stats for a 32-bit little-endian WAV."""

    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        nframes = handle.getnframes()
        raw = handle.readframes(nframes)

    if channels < 1 or width != SAMPLE_WIDTH or nframes < 1:
        raise ValueError(
            f"unsupported WAV: channels={channels} width={width} frames={nframes}"
        )

    count = nframes * channels
    samples = struct.unpack("<" + ("i" * count), raw)
    peak = max(abs(sample) for sample in samples)
    mean_square = sum(sample * sample for sample in samples) / count
    rms = mean_square**0.5
    full_scale = 2**31 - 1
    clipped = peak >= full_scale and sum(1 for sample in samples if abs(sample) >= full_scale) / count > 0.5
    return {
        "frames": nframes,
        "channels": channels,
        "rate": rate,
        "peak": peak,
        "rms": rms,
        "all_zero": peak == 0,
        "clipped": clipped,
    }


def arecord_command(device: str, duration: int, output: Path) -> list[str]:
    return [
        "arecord",
        "-D",
        device,
        "-c",
        str(CHANNELS),
        "-r",
        str(SAMPLE_RATE),
        "-f",
        SAMPLE_FORMAT,
        "-d",
        str(duration),
        str(output),
    ]


def capture(device: str, duration: int, output: Path) -> None:
    if duration < 1:
        raise SystemExit("duration must be at least 1 second")
    if shutil.which("arecord") is None:
        raise SystemExit("arecord is not installed (package alsa-utils)")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = arecord_command(device, duration, output)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size <= 44:
        detail = (result.stderr or result.stdout or "arecord failed").strip()
        raise SystemExit(detail or f"arecord exited {result.returncode}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Capture a mono 48 kHz WAV from the OwlCam I2S microphone.",
    )
    parser.add_argument("--duration", type=int, default=10, help="seconds to record")
    parser.add_argument(
        "--output",
        required=True,
        help="WAV destination path",
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help=f"ALSA device (default: {DEFAULT_DEVICE})",
    )
    args = parser.parse_args(argv)
    capture(args.device, args.duration, Path(args.output).expanduser())
    print(f"wrote {args.output}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
