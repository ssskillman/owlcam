from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
SPECIES_FILE = PACKAGE_ROOT / "species.txt"

YOLO_MODEL = os.environ.get("ANIMAL_ID_YOLO_MODEL", "yolov8n.pt")
YOLO_MIN_CONFIDENCE = float(os.environ.get("ANIMAL_ID_YOLO_MIN_CONFIDENCE", "0.20"))
UNKNOWN_THRESHOLD = float(os.environ.get("ANIMAL_ID_UNKNOWN_THRESHOLD", "0.60"))
ALTERNATIVES = 3
MAX_IMAGES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
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
