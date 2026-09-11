from __future__ import annotations

from functools import lru_cache

from animal_identifier.config import BIOCLIP_MODEL, YOLO_MODEL


def inference_device():
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@lru_cache(maxsize=1)
def load_yolo(model_name: str = YOLO_MODEL):
    from ultralytics import YOLO

    return YOLO(model_name)


@lru_cache(maxsize=1)
def load_bioclip():
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(BIOCLIP_MODEL)
    tokenizer = open_clip.get_tokenizer(BIOCLIP_MODEL)
    model = model.to(inference_device())
    model.eval()
    return model, preprocess, tokenizer
