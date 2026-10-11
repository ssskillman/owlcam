"""Buddy-house / travel stream checks (local HLS, Wi‑Fi, upload hint)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from field_mode import HOME_BITRATE, read_field_mode_config

HLS_PORT = int(os.environ.get("OWLCAM_HLS_PORT", "8888"))
STREAM_PATH = os.environ.get("OWLCAM_STREAM_PATH", "owl")
USB_STREAM_PATH = os.environ.get("OWLCAM_USB_STREAM_PATH", "owl2")
USB_BITRATE = int(os.environ.get("OWLCAM_USB_BITRATE", "2000000"))


def probe_local_hls(
    path: str = STREAM_PATH,
    *,
    port: int = HLS_PORT,
    timeout: float = 5,
) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}/{path}/index.m3u8"
    started = time.monotonic()
    opener = build_opener(HTTPRedirectHandler())
    request = Request(url, method="GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            response.read(512)
            code = response.status
    except HTTPError as exc:
        code = exc.code
    except (URLError, TimeoutError, OSError):
        return {
            "path": path,
            "ok": False,
            "httpCode": None,
            "latencyMs": round((time.monotonic() - started) * 1000),
            "note": "Could not reach local MediaMTX HLS.",
        }
    latency_ms = round((time.monotonic() - started) * 1000)
    ok = code == 200
    note = None
    if not ok:
        note = (
            "Local playlist not OK — restart owlcam-stream and check "
            "journalctl --user -u owlcam-stream."
        )
    return {
        "path": path,
        "ok": ok,
        "httpCode": code,
        "latencyMs": latency_ms,
        "note": note,
    }


def tailscale_exposure(run: Callable[..., Any]) -> str | None:
    try:
        result = run(
            ["tailscale", "serve", "status", "--json"],
            timeout=4,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    funnel = data.get("AllowFunnel")
    if isinstance(funnel, dict) and any(value is True for value in funnel.values()):
        return "public"
    return "private"


def estimate_upload_mbps(
    *,
    nest_active: bool,
    usb_active: bool,
    nest_bitrate: int,
) -> float:
    total_bps = 0
    if nest_active:
        total_bps += nest_bitrate
    if usb_active:
        total_bps += USB_BITRATE
    # Rough headroom for audio + HLS overhead.
    return round((total_bps * 1.15) / 1_000_000, 2)


def upload_hint_mbps(estimate: float, local_hls_ok: bool) -> str:
    if not local_hls_ok:
        return "Fix local HLS before worrying about upload."
    if estimate >= 4:
        return (
            f"~{estimate} Mbps encode+overhead — slow on many guest Wi‑Fi links. "
            "Enable field mode or stop USB."
        )
    if estimate >= 2.5:
        return (
            f"~{estimate} Mbps — may buffer on weak upload. Field mode helps."
        )
    return f"~{estimate} Mbps nest-only — usually fine if Wi‑Fi is stable."


def collect_preflight(
    *,
    run: Callable[..., Any],
    wifi_connection: Callable[[], str | None],
    service_state: Callable[[str], str],
    stream_unit: str,
    stream_usb_unit: str,
) -> dict[str, Any]:
    nest_state = service_state(stream_unit)
    usb_state = service_state(stream_usb_unit)
    nest_active = nest_state in ("active", "activating")
    usb_active = usb_state in ("active", "activating")
    field = read_field_mode_config()
    nest_bitrate = field["nestBitrate"] if field["enabled"] else HOME_BITRATE
    local_hls = probe_local_hls()
    estimate = estimate_upload_mbps(
        nest_active=nest_active,
        usb_active=usb_active,
        nest_bitrate=nest_bitrate,
    )
    return {
        "wifiConnection": wifi_connection(),
        "tailscaleExposure": tailscale_exposure(run),
        "streams": {
            "nest": {"state": nest_state, "active": nest_active},
            "usb": {"state": usb_state, "active": usb_active},
        },
        "fieldMode": field,
        "localHls": local_hls,
        "estimatedUploadMbps": estimate,
        "uploadHint": upload_hint_mbps(estimate, local_hls["ok"]),
    }


def _cli_run(command: list[str], *, timeout: float = 4) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _cli_wifi_connection() -> str | None:
    result = _cli_run(
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", "wlan0"],
        timeout=2,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value and value != "--" else None


def _cli_service_state(unit: str) -> str:
    result = _cli_run(["systemctl", "--user", "is-active", unit], timeout=4)
    state = result.stdout.strip()
    return state if state else "unknown"


def main() -> None:
    payload = collect_preflight(
        run=_cli_run,
        wifi_connection=_cli_wifi_connection,
        service_state=_cli_service_state,
        stream_unit="owlcam-stream.service",
        stream_usb_unit="owlcam-stream-usb.service",
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
