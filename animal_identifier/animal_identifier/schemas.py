from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]


@dataclass
class Alternative:
    species: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {"species": self.species, "confidence": round(self.confidence, 4)}


@dataclass
class ImageResult:
    file_name: str
    classification: str = "unknown"
    display_name: str = "Unknown animal"
    confidence: float = 0.0
    is_unknown: bool = True
    selected_source: str | None = None
    yolo_detection: dict[str, Any] | None = None
    alternatives: list[Alternative] = field(default_factory=list)
    best_candidate: str | None = None
    annotated_jpeg: bytes | None = None
    error: str | None = None
    model_version: str = ""

    def public_dict(self, *, annotated_image_url: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "file_name": self.file_name,
            "classification": self.classification,
            "display_name": self.display_name,
            "confidence": round(self.confidence, 4),
            "is_unknown": self.is_unknown,
            "selected_source": self.selected_source,
            "yolo_detection": self.yolo_detection,
            "alternatives": [item.as_dict() for item in self.alternatives],
            "model_version": self.model_version,
        }
        if self.is_unknown:
            payload["best_candidate"] = self.best_candidate
        if self.error:
            payload["error"] = self.error
        if annotated_image_url:
            payload["annotated_image_url"] = annotated_image_url
        return payload
