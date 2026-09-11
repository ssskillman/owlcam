from io import BytesIO

import pytest
from PIL import Image

from animal_identifier.pipeline import (
    Detection,
    InvalidImage,
    classify_image,
    display_name,
    load_species,
    move_to_device,
    select_primary_detection,
    validate_image,
)


def _png(width: int = 32, height: int = 32) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(20, 80, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_species_list_is_server_owned_and_includes_unknown():
    species = load_species()
    assert "barred owl" in species
    assert "unknown animal" in species
    assert "human" not in species


def test_species_list_covers_animals_from_outside_north_carolina():
    # A closed NC-only list forces visitor uploads into the nearest local
    # species: an ostrich came back as "wild turkey" at 0.99 confidence.
    species = load_species()
    for name in ("ostrich", "elephant", "kangaroo", "chicken", "penguin"):
        assert name in species


def test_display_name_title_cases_without_yelling_apostrophes():
    assert display_name("cooper's hawk") == "Cooper's hawk"
    assert display_name("barred owl") == "Barred owl"


def test_largest_animal_box_is_preferred_over_cars_and_people():
    detections = [
        Detection("person", 0.9, (0, 0, 400, 400)),
        Detection("car", 0.95, (0, 0, 800, 800)),
        Detection("bird", 0.4, (10, 10, 60, 80)),
    ]
    chosen = select_primary_detection(detections)
    assert chosen is not None
    assert chosen.label == "bird"


def test_giraffe_crop_is_used_only_without_a_preferred_animal():
    bird = Detection("bird", 0.4, (10, 10, 60, 80))
    giraffe = Detection("giraffe", 0.95, (0, 0, 800, 800))

    assert select_primary_detection([giraffe, bird]) == bird
    assert select_primary_detection([giraffe]) == giraffe


def test_no_animal_box_means_whole_image_only():
    assert select_primary_detection([Detection("person", 0.9, (0, 0, 10, 10))]) is None
    assert select_primary_detection([]) is None


def test_whole_image_wins_when_its_top_score_is_higher():
    def detect(_image):
        return [Detection("bird", 0.82, (1, 1, 10, 10))]

    def classify(image, _species):
        if image.size == (9, 9):
            return [
                ("cooper's hawk", 0.576),
                ("barred owl", 0.2),
                ("red-tailed hawk", 0.1),
            ]
        return [
            ("barred owl", 1.0),
            ("great horned owl", 0.0),
            ("eastern screech owl", 0.0),
        ]

    result = classify_image(
        _png(32, 32),
        file_name="backyard-owl.jpg",
        detect_fn=detect,
        classify_fn=classify,
    )
    assert result.classification == "barred owl"
    assert result.display_name == "Barred owl"
    assert result.confidence == 1.0
    assert result.is_unknown is False
    assert result.selected_source == "whole_image"
    assert result.yolo_detection is not None
    assert result.yolo_detection["label"] == "bird"
    assert [item.species for item in result.alternatives] == [
        "great horned owl",
        "eastern screech owl",
    ]


def test_below_threshold_is_unknown_and_keeps_best_candidate():
    def classify(_image, _species):
        return [("cooper's hawk", 0.48), ("barred owl", 0.3), ("crow", 0.1)]

    result = classify_image(
        _png(),
        file_name="blurry.jpg",
        detect_fn=lambda _image: [],
        classify_fn=classify,
        unknown_threshold=0.60,
    )
    assert result.is_unknown is True
    assert result.classification == "unknown"
    assert result.display_name == "Unknown animal"
    assert result.best_candidate == "cooper's hawk"
    assert result.confidence == 0.48


def test_one_bad_image_does_not_fail_the_batch(monkeypatch):
    from animal_identifier.pipeline import identify_images

    calls = {"n": 0}

    def classify(_image, _species):
        calls["n"] += 1
        return [("barred owl", 0.91), ("great horned owl", 0.05), ("crow", 0.04)]

    results = identify_images(
        [
            ("good.png", _png()),
            ("bad.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
            ("also-good.png", _png()),
        ],
        detect_fn=lambda _image: [],
        classify_fn=classify,
    )
    assert results[0].error is None
    assert results[1].error
    assert results[2].error is None
    assert results[0].classification == "barred owl"
    assert results[2].classification == "barred owl"


def test_one_inference_error_does_not_fail_the_batch():
    calls = {"n": 0}

    def classify(_image, _species):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model failed")
        return [("barred owl", 0.91), ("crow", 0.05), ("fox", 0.04)]

    from animal_identifier.pipeline import identify_images

    results = identify_images(
        [("failed.png", _png()), ("good.png", _png())],
        detect_fn=lambda _image: [],
        classify_fn=classify,
    )

    assert results[0].error
    assert results[1].classification == "barred owl"


def test_rejects_svg_and_html_even_with_image_extensions():
    with pytest.raises(InvalidImage):
        validate_image(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "trick.png")
    with pytest.raises(InvalidImage):
        validate_image(b"<!doctype html><html></html>", "page.jpg")


def test_rejects_disallowed_raster_format_with_allowed_extension():
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="green").save(buffer, format="GIF")

    with pytest.raises(InvalidImage):
        validate_image(buffer.getvalue(), "renamed.jpg")


def test_inference_device_prefers_cuda_when_available(monkeypatch):
    import types

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: True),
        device=lambda name: name,
    )
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)

    from animal_identifier.models import inference_device

    assert inference_device() == "cuda"


def test_load_bioclip_moves_model_onto_the_inference_device(monkeypatch):
    import sys
    import types

    from animal_identifier import models

    captured = {}

    class FakeModel:
        def eval(self):
            captured["eval"] = True
            return self

        def to(self, device):
            captured["device"] = device
            return self

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: True),
        device=lambda name: name,
    )
    fake_open_clip = types.SimpleNamespace(
        create_model_and_transforms=lambda *_args, **_kwargs: (
            FakeModel(),
            object(),
            object(),
        ),
        get_tokenizer=lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "open_clip", fake_open_clip)
    models.load_bioclip.cache_clear()

    model, _preprocess, _tokenizer = models.load_bioclip()

    assert captured["eval"] is True
    assert captured["device"] == "cuda"
    assert model is not None
    models.load_bioclip.cache_clear()


def test_move_to_device_sends_tensors_to_cuda():
    class FakeTensor:
        def to(self, device):
            self.device = device
            return self

    tensor = FakeTensor()
    moved = move_to_device(tensor, "cuda")
    assert moved.device == "cuda"


def test_accepts_png_and_strips_exif():
    image = Image.new("RGB", (16, 16), color="green")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    loaded = validate_image(buffer.getvalue(), "nest.jpg")
    assert loaded.mode == "RGB"
    assert loaded.info.get("exif") in (None, b"")
