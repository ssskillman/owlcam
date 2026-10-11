"""Field trip mode: lower nest bitrate and keep USB stream off."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

HOME_BITRATE = 2_500_000
FIELD_BITRATE = 1_500_000

DEFAULT_FIELD_MODE_FILE = Path(
    os.environ.get(
        "OWLCAM_FIELD_MODE_FILE",
        os.path.expanduser("~/.config/owlcam/field-mode.env"),
    )
)


def field_mode_path() -> Path:
    return DEFAULT_FIELD_MODE_FILE


def read_field_mode_config(path: Path | None = None) -> dict[str, Any]:
    env_path = path or field_mode_path()
    enabled = False
    bitrate = HOME_BITRATE
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("OWLCAM_FIELD_MODE="):
                enabled = stripped.split("=", 1)[1].strip() == "1"
            elif stripped.startswith("OWLCAM_BITRATE="):
                try:
                    bitrate = int(stripped.split("=", 1)[1].strip())
                except ValueError:
                    pass
    return {
        "enabled": enabled,
        "nestBitrate": bitrate,
        "homeBitrate": HOME_BITRATE,
        "fieldBitrate": FIELD_BITRATE,
        "configPath": str(env_path),
    }


def write_field_mode_env(enabled: bool, path: Path | None = None) -> None:
    env_path = path or field_mode_path()
    if enabled:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            f"OWLCAM_FIELD_MODE=1\nOWLCAM_BITRATE={FIELD_BITRATE}\n",
            encoding="utf-8",
        )
    else:
        env_path.unlink(missing_ok=True)


def apply_field_mode(
    enabled: bool,
    *,
    run: Callable[..., Any],
    stream_unit: str,
    stream_usb_unit: str,
    path: Path | None = None,
) -> dict[str, Any]:
    write_field_mode_env(enabled, path)
    if enabled:
        run(["systemctl", "--user", "stop", stream_usb_unit], timeout=10)
    restart = run(["systemctl", "--user", "restart", stream_unit], timeout=20)
    if restart.returncode != 0:
        raise RuntimeError("field mode stream restart failed")
    return field_mode_status(
        run=run,
        stream_unit=stream_unit,
        stream_usb_unit=stream_usb_unit,
        path=path,
    )


def field_mode_status(
    *,
    run: Callable[..., Any],
    stream_unit: str,
    stream_usb_unit: str,
    path: Path | None = None,
) -> dict[str, Any]:
    config = read_field_mode_config(path)
    nest_state = run(["systemctl", "--user", "is-active", stream_unit], timeout=4)
    usb_state = run(["systemctl", "--user", "is-active", stream_usb_unit], timeout=4)
    nest = nest_state.stdout.strip() or "unknown"
    usb = usb_state.stdout.strip() or "unknown"
    return {
        **config,
        "nestStreamState": nest,
        "usbStreamState": usb,
        "usbStopped": usb not in ("active", "activating"),
    }
