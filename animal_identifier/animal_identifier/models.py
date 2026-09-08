from __future__ import annotations

from functools import lru_cache

from animal_identifier.config import BIOCLIP_MODEL, YOLO_MODEL


@lru_cache(maxsize=1)
def load_yolo(model_name: str = YOLO_MODEL):
    from ultralytics import YOLO

    return YOLO(model_name)


@lru_cache(maxsize=1)
def load_bioclip():
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(BIOCLIP_MODEL)
    tokenizer = open_clip.get_tokenizer(BIOCLIP_MODEL)
    model.eval()
    return model, preprocess, tokenizer
