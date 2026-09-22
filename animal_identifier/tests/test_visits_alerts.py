from io import BytesIO
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient

from animal_identifier import server
from animal_identifier.schemas import ImageResult
from animal_identifier.store import AlertCooldownStore, VisitStore


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(10, 40, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_feed_watcher_visit_persists_and_lists(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "visits", VisitStore(tmp_path / "v.sqlite", tmp_path / "thumbs"))
    monkeypatch.setattr(
        server,
        "alert_cooldowns",
        AlertCooldownStore(tmp_path / "alerts.sqlite"),
    )
    monkeypatch.setattr(server, "identifications", server.IdentificationStore(tmp_path / "h.sqlite"))

    def fake_identify(files):
        jpeg = BytesIO()
        Image.new("RGB", (8, 8), color="orange").save(jpeg, format="JPEG")
        return [
            ImageResult(
                file_name=files[0][0],
                classification="barred owl",
                display_name="Barred owl",
                confidence=0.91,
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
        headers={"X-OwlCam-Source": "feed_watcher"},
        files=[("images", ("nest.jpg", _png(), "image/jpeg"))],
    )
    assert response.status_code == 200
    visits = client.get("/api/animal-identification/visits").json()["visits"]
    assert len(visits) == 1
    assert visits[0]["species"] == "barred owl"
    assert visits[0]["source"] == "feed_watcher"
    thumb = client.get(visits[0]["thumbnail_url"])
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"


def test_visit_dedupe_for_feed_watcher(monkeypatch, tmp_path):
    visit_store = VisitStore(tmp_path / "v.sqlite", tmp_path / "thumbs")
    monkeypatch.setattr(server, "visits", visit_store)
    monkeypatch.setattr(
        server,
        "alert_cooldowns",
        AlertCooldownStore(tmp_path / "alerts.sqlite"),
    )
    monkeypatch.setattr(server, "identifications", server.IdentificationStore(tmp_path / "h.sqlite"))

    def fake_identify(files):
        jpeg = BytesIO()
        Image.new("RGB", (8, 8), color="orange").save(jpeg, format="JPEG")
        return [
            ImageResult(
                file_name=files[0][0],
                classification="raccoon",
                display_name="Raccoon",
                confidence=0.88,
                is_unknown=False,
                annotated_jpeg=jpeg.getvalue(),
                model_version="test",
            )
        ]

    monkeypatch.setattr(server, "identify_images", fake_identify)
    client = TestClient(server.app)
    headers = {"X-OwlCam-Source": "feed_watcher"}
    for _ in range(2):
        client.post(
            "/api/animal-identification",
            headers=headers,
            files=[("images", ("x.jpg", _png(), "image/jpeg"))],
        )
    visits = client.get("/api/animal-identification/visits").json()["visits"]
    assert len(visits) == 1


def test_slack_alert_respects_cooldown(monkeypatch, tmp_path):
    monkeypatch.setenv("ANIMAL_ID_ALERT_SLACK_WEBHOOK", "https://hooks.slack.test/abc")
    monkeypatch.setenv("ANIMAL_ID_ALERT_SPECIES", "raccoon")
    monkeypatch.setenv("ANIMAL_ID_ALERT_COOLDOWN_SECONDS", "1800")
    import animal_identifier.alerts as alerts_mod

    monkeypatch.setattr(alerts_mod, "ALERT_SLACK_WEBHOOK", "https://hooks.slack.test/abc")
    monkeypatch.setattr(alerts_mod, "ALERT_SPECIES", frozenset({"raccoon"}))
    monkeypatch.setattr(alerts_mod, "ALERT_COOLDOWN_SECONDS", 1800)

    cooldowns = AlertCooldownStore(tmp_path / "alerts.sqlite")
    sent = []

    def fake_urlopen(request, timeout=15):
        sent.append(request.full_url)
        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"ok"

        return Resp()

    with patch("urllib.request.urlopen", fake_urlopen):
        assert alerts_mod.maybe_send_species_alert(
            species="raccoon",
            confidence=0.9,
            source="feed_watcher",
            cooldowns=cooldowns,
        )
        assert not alerts_mod.maybe_send_species_alert(
            species="raccoon",
            confidence=0.9,
            source="feed_watcher",
            cooldowns=cooldowns,
        )
    assert len(sent) == 1
