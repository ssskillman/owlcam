#!/usr/bin/env python3
"""Loopback IR control service: GPIO, auto motion, and status API."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ir_controller import (  # noqa: E402
    IRController,
    IrConfig,
    IrMode,
    is_dark_now,
    open_gpio_backend,
)

HOST = "127.0.0.1"
PORT = int(os.environ.get("OWLCAM_IR_PORT", "8767"))
RTSP_URL = os.environ.get("OWLCAM_RTSP_URL", "rtsp://127.0.0.1:8554/owl")
MOTION_INTERVAL = float(os.environ.get("OWLCAM_IR_MOTION_INTERVAL_SECONDS", "2"))
MOTION_THRESHOLD = float(os.environ.get("OWLCAM_IR_MOTION_THRESHOLD", "8.0"))
TICK_INTERVAL = float(os.environ.get("OWLCAM_IR_TICK_INTERVAL_SECONDS", "1"))


class IrService:
    def __init__(self) -> None:
        self.config = IrConfig.from_environ()
        self.controller = IRController(
            config=self.config,
            gpio=open_gpio_backend(self.config.gpio),
        )
        self._stop = threading.Event()
        self._prev_luma: float | None = None
        self._worker = threading.Thread(target=self._run_loop, name="ir-auto", daemon=True)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        self.controller.cleanup()

    def _run_loop(self) -> None:
        last_motion = 0.0
        last_tick = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_tick >= TICK_INTERVAL:
                self.controller.tick()
                last_tick = now
            if self.controller.mode == IrMode.AUTO and now - last_motion >= MOTION_INTERVAL:
                last_motion = now
                if is_dark_now(self.config) and self._motion_detected():
                    self.controller.pulse(reason="motion")
            time.sleep(0.25)

    def _motion_detected(self) -> bool:
        frame = self._grab_luma_sample()
        if frame is None:
            return False
        luma, _samples = frame
        if self._prev_luma is None:
            self._prev_luma = luma
            return False
        delta = abs(luma - self._prev_luma)
        self._prev_luma = luma
        return delta >= MOTION_THRESHOLD

    def _grab_luma_sample(self) -> tuple[float, int] | None:
        command = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            RTSP_URL,
            "-frames:v",
            "1",
            "-vf",
            "scale=64:36,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                timeout=20,
                capture_output=True,
            )
            data = result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None
        if not data:
            return None
        total = sum(data)
        return total / len(data), len(data)

    def set_mode(self, mode: str) -> None:
        try:
            parsed = IrMode(mode)
        except ValueError:
            raise ValueError("invalid mode") from None
        self.controller.set_mode(parsed)

    def status(self) -> dict[str, Any]:
        payload = self.controller.status()
        payload["sampledAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return payload


class IrHandler(BaseHTTPRequestHandler):
    server_version = "OwlCamIR"
    sys_version = ""

    @property
    def service(self) -> IrService:
        return self.server.ir_service

    def _path(self) -> str:
        return urlsplit(self.path).path

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self._path() == "/api/ir/status":
            self._send_json(HTTPStatus.OK, self.service.status())
            return
        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"error": {"code": "NOT_FOUND", "message": "Not found"}},
        )

    def do_POST(self) -> None:
        path = self._path()
        if path != "/api/ir/mode":
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "NOT_FOUND", "message": "Not found"}},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 4096:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "BODY_SIZE", "message": "Invalid body"}},
            )
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "INVALID_JSON", "message": "Invalid JSON"}},
            )
            return
        mode = payload.get("mode")
        if not isinstance(mode, str):
            self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": {"code": "INVALID_INPUT", "message": "mode required"}},
            )
            return
        try:
            self.service.set_mode(mode)
        except ValueError:
            self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": {"code": "INVALID_INPUT", "message": "Unknown mode"}},
            )
            return
        self._send_json(HTTPStatus.OK, self.service.status())

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    service = IrService()
    server = ThreadingHTTPServer((HOST, PORT), IrHandler)
    server.ir_service = service
    service.start()
    LOG = logging.getLogger("owlcam.ir")
    LOG.info("IR service listening on %s:%s gpio=%s", HOST, PORT, service.config.gpio)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
