#!/usr/bin/env python3
"""Tailnet-only, read-only health endpoint for the OwlCam dashboard."""

from __future__ import annotations

import fcntl
import json
import os
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = int(os.environ.get("OWLCAM_DIAGNOSTICS_PORT", "8765"))
ALLOWED_ORIGIN = os.environ.get(
    "OWLCAM_DIAGNOSTICS_ORIGIN",
    "https://carver-owlcam-72343.web.app",
)
PROCESS_NAMES = {
    "mediamtx": "mediamtx",
    "camera": "rpicam-vid",
    "ffmpeg": "ffmpeg",
}
I2C_SLAVE = 0x0703
BME280_CHIP_ID = 0x60
BME280_ADDRESSES = (0x76, 0x77)
DISCONNECTED_CLIMATE = {
    "connected": False,
    "sensor": None,
    "temperatureC": None,
    "humidityPercent": None,
}


def _read_kib_value(path: Path, key: str) -> int:
    for line in path.read_text().splitlines():
        name, separator, value = line.partition(":")
        if separator and name == key:
            return int(value.split()[0])
    raise ValueError(f"{key} is missing")


def _running_process_names(proc_root: Path) -> set[str]:
    names: set[str] = set()
    for process in proc_root.iterdir():
        if not process.name.isdigit():
            continue
        try:
            names.add((process / "comm").read_text().strip())
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return names


def _u16(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def _s16(lo: int, hi: int) -> int:
    value = _u16(lo, hi)
    return value - 65536 if value & 0x8000 else value


def _s8(value: int) -> int:
    return value - 256 if value & 0x80 else value


def compensate_bme280(
    calib: dict[str, int],
    *,
    adc_t: int,
    adc_h: int,
) -> tuple[float, float, int]:
    """Bosch integer compensation. Returns °C, %RH, and t_fine."""

    var1 = ((((adc_t >> 3) - (calib["dig_T1"] << 1))) * calib["dig_T2"]) >> 11
    var2 = (
        (
            (((adc_t >> 4) - calib["dig_T1"]) * ((adc_t >> 4) - calib["dig_T1"]))
            >> 12
        )
        * calib["dig_T3"]
    ) >> 14
    t_fine = var1 + var2
    temperature_c = ((t_fine * 5 + 128) >> 8) / 100

    humidity = t_fine - 76800
    humidity = (
        (
            (
                (
                    (adc_h << 14)
                    - (calib["dig_H4"] << 20)
                    - (calib["dig_H5"] * humidity)
                )
                + 16384
            )
            >> 15
        )
        * (
            (
                (
                    (
                        (
                            ((humidity * calib["dig_H6"]) >> 10)
                            * (((humidity * calib["dig_H3"]) >> 11) + 32768)
                        )
                        >> 10
                    )
                    + 2097152
                )
                * calib["dig_H2"]
                + 8192
            )
            >> 14
        )
    )
    humidity = humidity - (
        ((((humidity >> 15) * (humidity >> 15)) >> 7) * calib["dig_H1"]) >> 4
    )
    humidity = max(0, min(419430400, humidity))
    humidity_percent = (humidity >> 12) / 1024

    return temperature_c, humidity_percent, t_fine


def _parse_bme280_calib(block_88: bytes, block_e1: bytes) -> dict[str, int]:
    h4 = (block_e1[3] << 4) | (block_e1[4] & 0x0F)
    h5 = (block_e1[5] << 4) | (block_e1[4] >> 4)
    if h4 & 0x800:
        h4 -= 4096
    if h5 & 0x800:
        h5 -= 4096
    return {
        "dig_T1": _u16(block_88[0], block_88[1]),
        "dig_T2": _s16(block_88[2], block_88[3]),
        "dig_T3": _s16(block_88[4], block_88[5]),
        "dig_H1": block_88[25],
        "dig_H2": _s16(block_e1[0], block_e1[1]),
        "dig_H3": block_e1[2],
        "dig_H4": h4,
        "dig_H5": h5,
        "dig_H6": _s8(block_e1[6]),
    }


def _i2c_open(bus_path: Path, address: int) -> int:
    fd = os.open(bus_path, os.O_RDWR)
    try:
        fcntl.ioctl(fd, I2C_SLAVE, address)
    except OSError:
        os.close(fd)
        raise
    return fd


def _i2c_write(fd: int, register: int, value: int) -> None:
    os.write(fd, bytes((register, value)))


def _i2c_read(fd: int, register: int, length: int) -> bytes:
    os.write(fd, bytes((register,)))
    data = os.read(fd, length)
    if len(data) != length:
        raise OSError("short I2C read")
    return data


def _read_bme280(bus_path: Path, address: int) -> dict[str, Any] | None:
    fd = _i2c_open(bus_path, address)
    try:
        chip_id = _i2c_read(fd, 0xD0, 1)[0]
        if chip_id != BME280_CHIP_ID:
            return None
        block_88 = _i2c_read(fd, 0x88, 26)
        block_e1 = _i2c_read(fd, 0xE1, 7)
        _i2c_write(fd, 0xF2, 0x01)
        _i2c_write(fd, 0xF4, 0x25)
        time.sleep(0.05)
        raw = _i2c_read(fd, 0xF7, 8)
    finally:
        os.close(fd)

    adc_t = (raw[3] << 12) | (raw[4] << 4) | (raw[5] >> 4)
    adc_h = (raw[6] << 8) | raw[7]
    temperature_c, humidity_percent, _t_fine = compensate_bme280(
        _parse_bme280_calib(block_88, block_e1),
        adc_t=adc_t,
        adc_h=adc_h,
    )
    return {
        "connected": True,
        "sensor": "bme280",
        "temperatureC": round(temperature_c, 1),
        "humidityPercent": round(humidity_percent, 1),
    }


def read_climate(*, bus_path: Path | None = None) -> dict[str, Any]:
    """Best-effort BME280 sample. Missing hardware is a first-class UI state."""

    bus = bus_path or Path(os.environ.get("OWLCAM_I2C_BUS", "/dev/i2c-1"))
    if not bus.exists():
        return dict(DISCONNECTED_CLIMATE)
    for address in BME280_ADDRESSES:
        try:
            sample = _read_bme280(bus, address)
        except OSError:
            continue
        if sample is not None:
            return sample
    return dict(DISCONNECTED_CLIMATE)


def collect_diagnostics(
    *,
    proc_root: Path = Path("/proc"),
    thermal_path: Path = Path("/sys/class/thermal/thermal_zone0/temp"),
    climate_reader: Any = None,
) -> dict[str, Any]:
    """Return only the small, allowlisted metric contract used by the UI."""

    temperature_c = int(thermal_path.read_text().strip()) / 1000
    memory_kib = _read_kib_value(proc_root / "meminfo", "MemAvailable")
    load_1 = float((proc_root / "loadavg").read_text().split()[0])
    running = _running_process_names(proc_root)
    processes = {
        label: process_name in running
        for label, process_name in PROCESS_NAMES.items()
    }

    reader = read_climate if climate_reader is None else climate_reader
    climate = reader()

    return {
        "temperatureC": round(temperature_c, 1),
        "memoryAvailableGiB": round(memory_kib / 1024 / 1024, 1),
        "load1": round(load_1, 2),
        "processes": processes,
        "allProcessesStable": all(processes.values()),
        "climate": climate,
        "sampledAt": datetime.now(UTC).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
    }


class DiagnosticsHandler(BaseHTTPRequestHandler):
    server_version = "OwlCamDiagnostics"
    sys_version = ""

    def _origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin == ALLOWED_ORIGIN

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin == ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        if not self._origin_is_allowed():
            self._send_json(403, {"error": "origin_not_allowed"})
            return

        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Max-Age", "600")
        if (
            self.headers.get("Access-Control-Request-Private-Network", "").lower()
            == "true"
        ):
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._origin_is_allowed():
            self._send_json(403, {"error": "origin_not_allowed"})
            return
        # Tailscale Serve can strip the configured /diagnostics mount point.
        if self.path.rstrip("/") not in ("", "/diagnostics"):
            self._send_json(404, {"error": "not_found"})
            return

        try:
            payload = collect_diagnostics()
        except (OSError, ValueError):
            self._send_json(503, {"error": "metrics_unavailable"})
            return
        self._send_json(200, payload)

    def log_message(self, _format: str, *_args: object) -> None:
        # Access logs add no value for a single polled endpoint and would write
        # a line every five seconds forever.
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DiagnosticsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
