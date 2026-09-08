from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

from animal_identifier import server
from animal_identifier.schemas import ImageResult


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(10, 40, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_identify_returns_public_payload_and_preview(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "feedback", server.FeedbackStore(tmp_path / "fb.sqlite"))

    def fake_identify(files):
        jpeg = BytesIO()
        Image.new("RGB", (8, 8), color="orange").save(jpeg, format="JPEG")
        return [
            ImageResult(
                file_name=files[0][0],
                classification="barred owl",
                display_name="Barred owl",
                confidence=0.96,
                is_unknown=False,
                selected_source="whole_image",
                annotated_jpeg=jpeg.getvalue(),
                model_version="test",
            )
        ]

    monkeypatch.setattr(server, "identify_images", fake_identify)
    client = TestClient(server.app)
    response = client.post(
        "/api/animal-identification",
        files=[("images", ("backyard-owl.jpg", _png(), "image/jpeg"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["display_name"] == "Barred owl"
    assert body["results"][0]["confidence"] == 0.96
    url = body["results"][0]["annotated_image_url"]
    assert "/api/animal-identification/jobs/" in url
    assert client.get(url).status_code == 200
    assert "local/" not in url
    assert "/Users/" not in str(body)


def test_feedback_endpoint_stores_without_training_by_default(monkeypatch, tmp_path):
    store = server.FeedbackStore(tmp_path / "fb.sqlite")
    monkeypatch.setattr(server, "feedback", store)
    client = TestClient(server.app)
    response = client.post(
        "/api/animal-identification/feedback",
        json={
            "file_name": "a.jpg",
            "classification": "barred owl",
            "looks_right": False,
            "correction": "great horned owl",
            "train_opt_in": False,
        },
    )
    assert response.status_code == 200
    import sqlite3

    with sqlite3.connect(store.path) as connection:
        row = connection.execute(
            "SELECT looks_right, correction, train_opt_in FROM feedback"
        ).fetchone()
    assert row == (0, "great horned owl", 0)
