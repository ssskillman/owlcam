import asyncio
from concurrent.futures import Future
from io import BytesIO
import sqlite3

from PIL import Image
from fastapi.testclient import TestClient
from starlette.requests import Request

from animal_identifier import server
from animal_identifier.config import MAX_FILE_BYTES, UNKNOWN_THRESHOLD
from animal_identifier.schemas import ImageResult


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(10, 40, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_identify_returns_public_payload_and_preview(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "feedback", server.FeedbackStore(tmp_path / "fb.sqlite"))
    history = server.IdentificationStore(tmp_path / "history.sqlite")
    monkeypatch.setattr(server, "identifications", history)

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
    assert body["results"][0]["unknown_threshold"] == UNKNOWN_THRESHOLD
    url = body["results"][0]["annotated_image_url"]
    assert "/api/animal-identification/jobs/" in url
    assert client.get(url).status_code == 200
    assert "local/" not in url
    assert "/Users/" not in str(body)
    assert client.get("/api/animal-identification/summary").json() == {
        "total": 1,
        "categories": [
            {
                "category": "bird",
                "count": 1,
                "species": [{"species": "barred owl", "count": 1}],
            }
        ],
    }


def test_unknown_results_do_not_inflate_identified_animal_history(monkeypatch, tmp_path):
    history = server.IdentificationStore(tmp_path / "history.sqlite")
    monkeypatch.setattr(server, "identifications", history)

    def fake_identify(files):
        jpeg = BytesIO()
        Image.new("RGB", (8, 8), color="gray").save(jpeg, format="JPEG")
        return [
            ImageResult(
                file_name=files[0][0],
                classification="unknown",
                display_name="Unknown animal",
                confidence=0.42,
                is_unknown=True,
                selected_source="whole_image",
                annotated_jpeg=jpeg.getvalue(),
                model_version="test",
            )
        ]

    monkeypatch.setattr(server, "identify_images", fake_identify)
    response = TestClient(server.app).post(
        "/api/animal-identification",
        files=[("images", ("unclear.jpg", _png(), "image/jpeg"))],
    )

    assert response.status_code == 200
    assert history.summary() == {"total": 0, "categories": []}


def test_history_write_failure_does_not_discard_identification(monkeypatch):
    class BrokenHistory:
        @staticmethod
        def add_many(_rows):
            raise sqlite3.OperationalError("database is locked")

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

    monkeypatch.setattr(server, "identifications", BrokenHistory())
    monkeypatch.setattr(server, "identify_images", fake_identify)
    response = TestClient(server.app).post(
        "/api/animal-identification",
        files=[("images", ("owl.jpg", _png(), "image/jpeg"))],
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["display_name"] == "Barred owl"


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


def test_oversized_file_returns_one_card_without_running_inference(monkeypatch):
    monkeypatch.setattr(
        server,
        "_identify_with_timeout",
        lambda _files: (_ for _ in ()).throw(AssertionError("inference ran")),
    )
    client = TestClient(server.app)

    response = client.post(
        "/api/animal-identification",
        files=[
            (
                "images",
                ("too-large.jpg", b"x" * (MAX_FILE_BYTES + 1), "image/jpeg"),
            )
        ],
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["error"] == (
        "That photo is larger than 10 MB."
    )


def test_client_ip_uses_proxy_appended_address_not_spoofed_first_hop():
    request = Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 1234),
            "headers": [
                (b"x-forwarded-for", b"203.0.113.99, 198.51.100.7"),
            ],
        }
    )

    assert server._client_ip(request) == "198.51.100.7"


def test_feedback_rejects_unbounded_text(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "feedback", server.FeedbackStore(tmp_path / "fb.sqlite"))
    client = TestClient(server.app)

    response = client.post(
        "/api/animal-identification/feedback",
        json={
            "looks_right": False,
            "note": "x" * 2001,
        },
    )

    assert response.status_code == 422


def test_request_body_limit_rejects_declared_and_streamed_oversize():
    called = False

    async def downstream(_scope, receive, _send):
        nonlocal called
        called = True
        while (await receive()).get("more_body"):
            pass

    async def run_request(headers, messages):
        sent = []
        incoming = iter(messages)

        async def receive():
            return next(incoming)

        async def send(message):
            sent.append(message)

        middleware = server.BodyLimitMiddleware(
            downstream,
            max_bytes=5,
            feedback_max_bytes=5,
        )
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/animal-identification",
            "headers": headers,
        }
        await middleware(scope, receive, send)
        return sent

    declared = asyncio.run(
        run_request(
            [(b"content-length", b"6")],
            [{"type": "http.request", "body": b"", "more_body": False}],
        )
    )
    streamed = asyncio.run(
        run_request(
            [],
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"456", "more_body": False},
            ],
        )
    )

    assert declared[0]["status"] == 413
    assert streamed[0]["status"] == 413
    assert called is True


def test_timeout_preserves_completed_card_and_does_not_queue_remaining(monkeypatch):
    completed = Future()
    completed.set_result(
        [ImageResult(file_name="good.jpg", classification="barred owl")]
    )
    timed_out = Future()
    futures = iter([completed, timed_out])
    submissions = []

    class Pool:
        def submit(self, _function, files):
            submissions.append(files)
            return next(futures)

    monkeypatch.setattr(server, "_pool", Pool())
    monkeypatch.setattr(server, "INFERENCE_TIMEOUT_SECONDS", 0.001)

    results = server._identify_with_timeout(
        [("good.jpg", b"a"), ("slow.jpg", b"b"), ("later.jpg", b"c")]
    )
    timed_out.set_result([ImageResult(file_name="slow.jpg")])

    assert results[0].classification == "barred owl"
    assert results[1].error
    assert results[2].error
    assert len(submissions) == 2


def test_openapi_marks_uploaded_images_as_binary_files():
    server.app.openapi_schema = None
    schema = server.app.openapi()
    body = schema["components"]["schemas"][
        "Body_identify_api_animal_identification_post"
    ]
    items = body["properties"]["images"]["items"]
    assert items["type"] == "string"
    assert items.get("format") == "binary"
    assert schema["openapi"].startswith("3.0")
