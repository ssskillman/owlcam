#!/usr/bin/env python3
"""Standalone GPIO test for the IR illuminator (run on the Pi)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ir_controller import IRController, IrConfig, IrMode, open_gpio_backend  # noqa: E402


def pi_health_lines() -> list[str]:
    lines: list[str] = []
    for command, label in (
        (["vcgencmd", "measure_temp"], "cpu_temp"),
        (["vcgencmd", "get_throttled"], "throttle"),
    ):
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"{label}={result.stdout.strip()}")
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
            lines.append(f"{label}=unavailable")
    return lines


def main(argv: list[str] | None = None) -> None:
    os.environ.setdefault("OWLCAM_IR_MOCK_GPIO", "0")
    parser = argparse.ArgumentParser(description="OwlCam IR GPIO test utility")
    parser.add_argument(
        "command",
        choices=("on", "off", "pulse", "status"),
        help="GPIO action",
    )
    parser.add_argument("--seconds", type=float, default=10.0, help="pulse duration")
    parser.add_argument(
        "--log-pi-health",
        action="store_true",
        help="log Pi temperature and throttling state",
    )
    args = parser.parse_args(argv)

    config = IrConfig.from_environ()
    controller = IRController(config=config, gpio=open_gpio_backend(config.gpio))
    if args.command != "status":
        controller.set_mode(IrMode.MANUAL_ON)

    def log_health(prefix: str) -> None:
        if not args.log_pi_health:
            return
        for line in pi_health_lines():
            print(f"{prefix} {line}")

    try:
        if args.command == "on":
            log_health("before")
            controller.on(reason="manual")
            log_health("during")
            print("IR on")
        elif args.command == "off":
            controller.off(reason="manual")
            log_health("after")
            print("IR off")
        elif args.command == "pulse":
            log_health("before")
            controller.on(reason="manual")
            time.sleep(max(0.0, args.seconds))
            controller.off(reason="manual")
            log_health("after")
            print(f"IR pulsed {args.seconds}s")
        else:
            print(controller.status())
    finally:
        controller.cleanup()


if __name__ == "__main__":
    main()
