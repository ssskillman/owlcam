#!/usr/bin/env python3
"""Tailnet-only, read-only health endpoint for the OwlCam dashboard."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

# owlcam-diagnostics and bme280_raw.py install side by side in ~/.local/bin.
_BIN_DIR = Path(__file__).resolve().parent
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

from bme280_raw import read_bme280  # noqa: E402


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
CLIMATE_POLL_SECONDS = int(os.environ.get("OWLCAM_CLIMATE_POLL_SECONDS", "30"))
HISTORY_SAMPLE_SECONDS = int(
    os.environ.get("OWLCAM_DIAGNOSTICS_HISTORY_SECONDS", "300")
)
HISTORY_RETENTION = timedelta(days=30)
HISTORY_MAX_HOURS = int(HISTORY_RETENTION.total_seconds() // 3600)
HISTORY_PATH = Path(
    os.environ.get(
        "OWLCAM_DIAGNOSTICS_HISTORY_PATH",
        Path.home() / ".local/state/owlcam/diagnostics-history.json",
    )
)

DISCONNECTED_CLIMATE: dict[str, Any] = {
    "connected": False,
    "sensor": None,
    "temperatureC": None,
    "humidityPercent": None,
    "pressureHpa": None,
    "sampledAt": None,
}

_climate_lock = threading.Lock()
_cached_climate: dict[str, Any] = dict(DISCONNECTED_CLIMATE)
_climate_worker_started = False


def _climate_sampled_at() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _climate_from_reading(reading: dict[str, float]) -> dict[str, Any]:
    return {
        "connected": True,
        "sensor": "bme280",
        "temperatureC": round(reading["temperature_c"], 1),
        "humidityPercent": round(reading["humidity_pct"], 1),
        "pressureHpa": round(reading["pressure_hpa"], 1),
        "sampledAt": _climate_sampled_at(),
    }


def _poll_climate_once() -> None:
    global _cached_climate

    try:
        reading = read_bme280()
        sample = _climate_from_reading(reading)
    except Exception as exc:
        print(f"BME280 error: {exc}", flush=True)
        sample = dict(DISCONNECTED_CLIMATE)
    with _climate_lock:
        _cached_climate = sample


def _climate_worker() -> None:
    while True:
        _poll_climate_once()
        time.sleep(CLIMATE_POLL_SECONDS)


def start_climate_worker() -> None:
    global _climate_worker_started

    if _climate_worker_started:
        return
    _climate_worker_started = True
    thread = threading.Thread(target=_climate_worker, name="owlcam-climate", daemon=True)
    thread.start()


def read_climate() -> dict[str, Any]:
    """Return the latest cached nest climate sample."""

    with _climate_lock:
        return dict(_cached_climate)


def set_climate_cache(climate: dict[str, Any]) -> None:
    """Test hook to inject climate without starting the worker."""

    global _cached_climate

    with _climate_lock:
        _cached_climate = dict(climate)


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


class HistoryStore:
    """Small, bounded JSON history for the dashboard's numeric metrics."""

    def __init__(
        self,
        path: Path,
        *,
        retention: timedelta = HISTORY_RETENTION,
        clock: Any = None,
    ) -> None:
        self.path = path
        self.retention = retention
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._samples = self._pruned(self._load())

    def _load(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        if not isinstance(payload, list):
            return []
        return [sample for sample in payload if isinstance(sample, dict)]

    def _cutoff(self) -> datetime:
        return self.clock() - self.retention

    def _pruned(self, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cutoff = self._cutoff()
        kept = []
        for sample in samples:
            try:
                sampled_at = datetime.fromisoformat(
                    str(sample["sampledAt"]).replace("Z", "+00:00")
                )
            except (KeyError, TypeError, ValueError):
                continue
            if sampled_at >= cutoff:
                kept.append(sample)
        return kept

    def add(self, diagnostics: dict[str, Any]) -> None:
        climate = diagnostics["climate"]
        sample = {
            "sampledAt": diagnostics["sampledAt"],
            "habitatTemperatureC": (
                climate["temperatureC"] if climate["connected"] else None
            ),
            "humidityPercent": (
                climate["humidityPercent"] if climate["connected"] else None
            ),
            "pressureHpa": climate["pressureHpa"] if climate["connected"] else None,
            "temperatureC": diagnostics["temperatureC"],
            "memoryAvailableGiB": diagnostics["memoryAvailableGiB"],
            "load1": diagnostics["load1"],
            "stableProcessCount": sum(diagnostics["processes"].values()),
        }
        with self._lock:
            self._samples = self._pruned([*self._samples, sample])
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._samples, separators=(",", ":")))
            temporary.replace(self.path)

    def samples(self, *, hours: int | None = None) -> list[dict[str, Any]]:
        window = self.retention if hours is None else timedelta(hours=hours)
        cutoff = self.clock() - window
        with self._lock:
            samples = list(self._samples)
        return [
            sample
            for sample in samples
            if datetime.fromisoformat(
                str(sample["sampledAt"]).replace("Z", "+00:00")
            )
            >= cutoff
        ]


_history_store = HistoryStore(HISTORY_PATH)


def history_payload(hours: int) -> dict[str, Any]:
    return {
        "samples": _history_store.samples(hours=hours),
        "sampleIntervalSeconds": HISTORY_SAMPLE_SECONDS,
    }


def _history_worker() -> None:
    while True:
        try:
            _history_store.add(collect_diagnostics())
        except (OSError, ValueError, KeyError) as exc:
            print(f"Diagnostics history error: {exc}", flush=True)
        time.sleep(HISTORY_SAMPLE_SECONDS)


def start_history_worker() -> None:
    thread = threading.Thread(
        target=_history_worker,
        name="owlcam-diagnostics-history",
        daemon=True,
    )
    thread.start()


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
        parsed = urlsplit(self.path)
        path = parsed.path.rstrip("/")
        if path in ("/history", "/diagnostics/history"):
            try:
                hours = int(
                    parse_qs(parsed.query).get("hours", [str(HISTORY_MAX_HOURS)])[0]
                )
            except ValueError:
                self._send_json(400, {"error": "invalid_history_window"})
                return
            if hours < 1 or hours > HISTORY_MAX_HOURS:
                self._send_json(400, {"error": "invalid_history_window"})
                return
            self._send_json(200, history_payload(hours))
            return
        # Tailscale Serve can strip the configured /diagnostics mount point.
        if path not in ("", "/diagnostics"):
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
    start_climate_worker()
    start_history_worker()
    server = ThreadingHTTPServer((HOST, PORT), DiagnosticsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
