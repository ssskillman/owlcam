#!/usr/bin/env python3
"""Grab stills from loopback RTSP, queue on disk, POST to the PC identify API."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LOG = logging.getLogger("owlcam.feed_watcher")

RTSP_URL = os.environ.get("OWLCAM_RTSP_URL", "rtsp://127.0.0.1:8554/owl")
IDENTIFY_URL = os.environ.get("OWLCAM_IDENTIFY_URL", "").strip()
OUTBOX = Path(os.environ.get("OWLCAM_OUTBOX", str(Path.home() / "owlcam" / "outbox")))
SENT = Path(os.environ.get("OWLCAM_SENT", str(Path.home() / "owlcam" / "sent")))
FAILED = Path(os.environ.get("OWLCAM_FAILED", str(Path.home() / "owlcam" / "failed")))
CAPTURE_INTERVAL = int(os.environ.get("OWLCAM_CAPTURE_INTERVAL_SECONDS", "30"))
QUEUE_RETRY = int(os.environ.get("OWLCAM_QUEUE_RETRY_SECONDS", "60"))
POST_TIMEOUT = int(os.environ.get("OWLCAM_POST_TIMEOUT_SECONDS", "90"))
MAX_OUTBOX = int(os.environ.get("OWLCAM_MAX_OUTBOX_FILES", "500"))
SOURCE_HEADER = "feed_watcher"


def ensure_dirs() -> None:
    for path in (OUTBOX, SENT, FAILED):
        path.mkdir(parents=True, exist_ok=True)


def outbox_files() -> list[Path]:
    return sorted(OUTBOX.glob("*.jpg"), key=lambda p: p.stat().st_mtime)


def trim_outbox() -> None:
    files = outbox_files()
    overflow = len(files) - MAX_OUTBOX
    if overflow <= 0:
        return
    for path in files[:overflow]:
        LOG.warning("outbox full; dropping oldest %s", path.name)
        path.unlink(missing_ok=True)


def grab_still(destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
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
        "-update",
        "1",
        "-q:v",
        "2",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True, timeout=45)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        LOG.warning("grab failed: %s", exc)
        destination.unlink(missing_ok=True)
        return False
    return destination.is_file() and destination.stat().st_size > 0


def capture_once() -> None:
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    path = OUTBOX / f"{stamp}.jpg"
    if grab_still(path):
        LOG.info("queued %s", path.name)
        trim_outbox()


def post_still(path: Path) -> tuple[bool, bool]:
    """Return (done, retry_later). done=True means file was moved out of outbox."""
    if not IDENTIFY_URL:
        LOG.error("OWLCAM_IDENTIFY_URL is not set")
        return False, True

    data = path.read_bytes()
    boundary = f"owlcam-{int(time.time())}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="images"; filename="{path.name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        IDENTIFY_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-OwlCam-Source": SOURCE_HEADER,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            LOG.warning("identify busy (%s); will retry %s", exc.code, path.name)
            return False, True
        LOG.warning("identify HTTP %s for %s", exc.code, path.name)
        shutil.move(str(path), str(FAILED / path.name))
        return True, False
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOG.warning("identify unreachable for %s: %s", path.name, exc)
        return False, True

    results = payload.get("results") or []
    if results:
        first = results[0]
        LOG.info(
            "classified %s -> %s unknown=%s conf=%s",
            path.name,
            first.get("classification"),
            first.get("is_unknown"),
            first.get("confidence"),
        )
    shutil.move(str(path), str(SENT / path.name))
    return True, False


def drain_queue_once() -> None:
    pending = outbox_files()
    if not pending:
        return
    path = pending[0]
    done, retry = post_still(path)
    if not done and retry:
        return


def run_loop() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if not IDENTIFY_URL:
        LOG.error("Set OWLCAM_IDENTIFY_URL in ~/.config/owlcam/watcher.env")
        sys.exit(2)
    ensure_dirs()
    LOG.info(
        "feed watcher started interval=%ss outbox=%s",
        CAPTURE_INTERVAL,
        OUTBOX,
    )
    last_capture = 0.0
    last_queue = 0.0
    while True:
        now = time.monotonic()
        if now - last_capture >= CAPTURE_INTERVAL:
            capture_once()
            last_capture = now
        if now - last_queue >= QUEUE_RETRY:
            drain_queue_once()
            last_queue = now
        time.sleep(1)


if __name__ == "__main__":
    run_loop()
