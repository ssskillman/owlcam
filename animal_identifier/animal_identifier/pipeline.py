from __future__ import annotations

import io
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFile, ImageFont

from animal_identifier.config import (
    ALLOWED_SUFFIXES,
    ALTERNATIVES,
    ANIMAL_LABELS,
    MAX_FILE_BYTES,
    MAX_IMAGE_PIXELS,
    MODEL_VERSION,
    PROMPT,
    SPECIES_FILE,
    UNKNOWN_THRESHOLD,
    YOLO_MIN_CONFIDENCE,
    YOLO_MODEL,
)
from animal_identifier.schemas import Alternative, Detection, ImageResult

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
ImageFile.LOAD_TRUNCATED_IMAGES = False

ClassifyFn = Callable[[Image.Image, Sequence[str]], list[tuple[str, float]]]
DetectFn = Callable[[Image.Image], list[Detection]]


class InvalidImage(ValueError):
    """Uploaded bytes are not a usable raster image."""


def load_species(path: Path = SPECIES_FILE) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        name = raw.strip().lower()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def display_name(species: str) -> str:
    if species == "unknown":
        return "Unknown animal"
    return species[:1].upper() + species[1:] if species else species


def select_primary_detection(detections: Sequence[Detection]) -> Detection | None:
    animals = [item for item in detections if item.label in ANIMAL_LABELS]
    if not animals:
        return None
    preferred = [item for item in animals if item.label != "giraffe"]
    candidates = preferred or animals
    return max(
        candidates,
        key=lambda item: (item.box[2] - item.box[0]) * (item.box[3] - item.box[1]),
    )


def validate_image(payload: bytes, file_name: str) -> Image.Image:
    if len(payload) > MAX_FILE_BYTES:
        raise InvalidImage("That photo is larger than 10 MB.")
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise InvalidImage("Use a JPG, PNG, or WebP photo.")
    lowered = payload.lstrip().lower()
    if lowered.startswith(b"<svg") or lowered.startswith(b"<!doctype html") or lowered.startswith(
        b"<html"
    ):
        raise InvalidImage("That file is not a photo.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as opened:
                if opened.format not in {"JPEG", "PNG", "WEBP"}:
                    raise InvalidImage("Use a JPG, PNG, or WebP photo.")
                opened.load()
                image = opened.convert("RGB")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("That photo is too large to open safely.") from exc
    except OSError as exc:
        raise InvalidImage("We couldn't read that photo.") from exc
    image.info.pop("exif", None)
    return image


def annotate(image: Image.Image, detections: Sequence[Detection]) -> bytes:
    output = image.copy().convert("RGB")
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default()
    for detection in detections:
        x1, y1, x2, y2 = detection.box
        text = f"{detection.label} {detection.confidence:.0%}"
        draw.rectangle((x1, y1, x2, y2), outline="#e8a43a", width=4)
        text_box = draw.textbbox((x1, y1), text, font=font)
        draw.rectangle(text_box, fill="#e8a43a")
        draw.text((x1, y1), text, fill="#0b100d", font=font)
    buffer = io.BytesIO()
    output.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def default_detect(image: Image.Image) -> list[Detection]:
    from animal_identifier.models import load_yolo

    model = load_yolo(YOLO_MODEL)
    result = model.predict(image, conf=YOLO_MIN_CONFIDENCE, verbose=False)[0]
    detections: list[Detection] = []
    for box in result.boxes:
        class_id = int(box.cls.item())
        xyxy = tuple(int(value) for value in box.xyxy[0].tolist())
        detections.append(
            Detection(result.names[class_id], float(box.conf.item()), xyxy)
        )
    return detections


def default_classify(image: Image.Image, species: Sequence[str]) -> list[tuple[str, float]]:
    import torch

    from animal_identifier.models import load_bioclip

    model, preprocess, tokenizer = load_bioclip()
    prompts = [PROMPT.format(name=name) for name in species]
    image_tensor = preprocess(image.convert("RGB")).unsqueeze(0)
    text_tokens = tokenizer(prompts)
    with torch.inference_mode():
        image_features = model.encode_image(image_tensor)
        text_features = model.encode_text(text_tokens)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        probabilities = (100 * image_features @ text_features.T).softmax(dim=-1)[0]
    values, indices = probabilities.topk(min(len(species), max(ALTERNATIVES + 1, 3)))
    return [
        (species[int(index)], float(score))
        for score, index in zip(values.tolist(), indices.tolist(), strict=True)
    ]


def classify_image(
    payload: bytes,
    *,
    file_name: str,
    detect_fn: DetectFn | None = None,
    classify_fn: ClassifyFn | None = None,
    unknown_threshold: float = UNKNOWN_THRESHOLD,
    species: Sequence[str] | None = None,
) -> ImageResult:
    detect = detect_fn or default_detect
    classify = classify_fn or default_classify
    names = list(species or load_species())
    try:
        image = validate_image(payload, file_name)
    except InvalidImage as exc:
        return ImageResult(file_name=file_name, error=str(exc), model_version=MODEL_VERSION)

    detections = detect(image)
    primary = select_primary_detection(detections)
    whole_scores = classify(image, names)
    crop_scores: list[tuple[str, float]] = []
    source = "whole_image"
    chosen = whole_scores
    if primary is not None:
        crop = image.crop(primary.box)
        crop_scores = classify(crop, names)
        if crop_scores and (
            not whole_scores or crop_scores[0][1] > whole_scores[0][1]
        ):
            chosen = crop_scores
            source = "crop"

    if not chosen:
        return ImageResult(
            file_name=file_name,
            error="We couldn't analyze this photo right now. Please try again in a moment.",
            model_version=MODEL_VERSION,
        )

    top_species, top_score = chosen[0]
    alternatives = [
        Alternative(species=name, confidence=score) for name, score in chosen[1:1 + ALTERNATIVES]
    ]
    unknown = top_score < unknown_threshold or top_species == "unknown animal"
    yolo_payload = None
    if primary is not None:
        yolo_payload = {
            "label": primary.label,
            "confidence": round(primary.confidence, 4),
            "box": list(primary.box),
        }
    return ImageResult(
        file_name=file_name,
        classification="unknown" if unknown else top_species,
        display_name="Unknown animal" if unknown else display_name(top_species),
        confidence=top_score,
        is_unknown=unknown,
        selected_source=source,
        yolo_detection=yolo_payload,
        alternatives=alternatives if not unknown else [
            Alternative(species=name, confidence=score) for name, score in chosen[1:1 + ALTERNATIVES]
        ],
        best_candidate=top_species if unknown else None,
        annotated_jpeg=annotate(image, [primary] if primary else detections[:1]),
        model_version=MODEL_VERSION,
    )


def identify_images(
    files: Sequence[tuple[str, bytes]],
    *,
    detect_fn: DetectFn | None = None,
    classify_fn: ClassifyFn | None = None,
) -> list[ImageResult]:
    results: list[ImageResult] = []
    for name, payload in files:
        try:
            result = classify_image(
                payload,
                file_name=name,
                detect_fn=detect_fn,
                classify_fn=classify_fn,
            )
        except Exception:
            result = ImageResult(
                file_name=name,
                error=(
                    "We couldn't analyze this photo right now. "
                    "Please try again in a moment."
                ),
                model_version=MODEL_VERSION,
            )
        results.append(result)
    return results
