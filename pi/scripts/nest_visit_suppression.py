#!/usr/bin/env python3
"""Hide nest visit cards on the public site when the inference host cannot delete yet."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

DEFAULT_PATH = Path.home() / ".config" / "owlcam" / "suppressed-nest-visits.json"
_lock = threading.Lock()


def suppression_path() -> Path:
    raw = os.environ.get("OWLCAM_SUPPRESSED_VISITS_FILE", "")
    return Path(raw) if raw else DEFAULT_PATH


def load_suppressed_ids() -> set[int]:
    path = suppression_path()
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    ids = payload.get("visitIds") if isinstance(payload, dict) else payload
    if not isinstance(ids, list):
        return set()
    result: set[int] = set()
    for value in ids:
        if isinstance(value, int) and value > 0:
            result.add(value)
    return result


def save_suppressed_ids(ids: set[int]) -> None:
    path = suppression_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    body = json.dumps({"visitIds": sorted(ids)}, indent=2)
    temporary.write_text(f"{body}\n", encoding="utf-8")
    temporary.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def suppress_visit(visit_id: int) -> None:
    if visit_id < 1:
        return
    with _lock:
        ids = load_suppressed_ids()
        ids.add(visit_id)
        save_suppressed_ids(ids)


def unsuppress_visit(visit_id: int) -> None:
    if visit_id < 1:
        return
    with _lock:
        ids = load_suppressed_ids()
        ids.discard(visit_id)
        save_suppressed_ids(ids)


def list_suppressed_payload() -> dict[str, list[int]]:
    return {"visitIds": sorted(load_suppressed_ids())}
