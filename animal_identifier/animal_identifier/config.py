from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
SPECIES_FILE = PACKAGE_ROOT / "species.txt"

YOLO_MODEL = os.environ.get("ANIMAL_ID_YOLO_MODEL", "yolov8n.pt")
YOLO_MIN_CONFIDENCE = float(os.environ.get("ANIMAL_ID_YOLO_MIN_CONFIDENCE", "0.20"))
UNKNOWN_THRESHOLD = float(os.environ.get("ANIMAL_ID_UNKNOWN_THRESHOLD", "0.60"))
# Fraction of the frame below which the subject is too small for the
# whole-image pass to resolve, and the crop is worth trusting over it.
SMALL_SUBJECT_FRACTION = float(os.environ.get("ANIMAL_ID_SMALL_SUBJECT", "0.10"))
ALTERNATIVES = 3
MAX_IMAGES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MODEL_VERSION = os.environ.get("ANIMAL_ID_MODEL_VERSION", "yolov8n+bioclip")
BIOCLIP_MODEL = "hf-hub:imageomics/bioclip"
PROMPT = "a wildlife camera photograph of a {name}"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ANIMAL_ID_CORS_ORIGINS",
        "https://owlcam.tail31318f.ts.net,https://carver-owlcam-72343.web.app",
    ).split(",")
    if origin.strip()
]

BIND_HOST = os.environ.get("ANIMAL_ID_HOST", "127.0.0.1")
BIND_PORT = int(os.environ.get("ANIMAL_ID_PORT", "8767"))
JOB_TTL_SECONDS = 24 * 60 * 60
RATE_LIMIT_REQUESTS = int(os.environ.get("ANIMAL_ID_RATE_LIMIT", "20"))
RATE_LIMIT_WINDOW_SECONDS = 15 * 60
INFERENCE_TIMEOUT_SECONDS = int(os.environ.get("ANIMAL_ID_INFERENCE_TIMEOUT", "120"))
VISIT_LOG_UNKNOWN = os.environ.get("ANIMAL_ID_VISIT_LOG_UNKNOWN", "0").strip() in {
    "1",
    "true",
    "yes",
}
VISIT_DEDUPE_SECONDS = int(os.environ.get("ANIMAL_ID_VISIT_DEDUPE_SECONDS", "300"))
VISIT_LIST_DEFAULT_LIMIT = int(os.environ.get("ANIMAL_ID_VISIT_LIST_LIMIT", "50"))
ALERT_SLACK_WEBHOOK = os.environ.get("ANIMAL_ID_ALERT_SLACK_WEBHOOK", "").strip()
ALERT_SPECIES = frozenset(
    name.strip().lower()
    for name in os.environ.get(
        "ANIMAL_ID_ALERT_SPECIES",
        "barred owl,raccoon",
    ).split(",")
    if name.strip()
)
ALERT_COOLDOWN_SECONDS = int(os.environ.get("ANIMAL_ID_ALERT_COOLDOWN_SECONDS", "1800"))

# COCO classes that are animals. Person/vehicle boxes must not steal the crop.
ANIMAL_LABELS = frozenset(
    {
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
        "mouse",
    }
)
