from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from animal_identifier.config import (
    BIND_HOST,
    BIND_PORT,
    CORS_ORIGINS,
    INFERENCE_TIMEOUT_SECONDS,
    MAX_FILE_BYTES,
    MAX_IMAGES,
    MODEL_VERSION,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    UNKNOWN_THRESHOLD,
)
from animal_identifier.pipeline import identify_images, load_species
from animal_identifier.schemas import ImageResult
from animal_identifier.store import FeedbackStore, JobStore

FAILURE = "We couldn't analyze this photo right now. Please try again in a moment."
DATA_DIR = Path(
    os.environ.get(
        "ANIMAL_ID_DATA_DIR",
        str(Path.home() / ".owlcam" / "animal-id"),
    )
)
MAX_REQUEST_BYTES = MAX_IMAGES * MAX_FILE_BYTES + 1_000_000
MAX_FEEDBACK_BYTES = 16 * 1024


class RequestTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int, feedback_max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.feedback_max_bytes = feedback_max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        if scope["path"] == "/api/animal-identification":
            max_bytes = self.max_bytes
        elif scope["path"] == "/api/animal-identification/feedback":
            max_bytes = self.feedback_max_bytes
        else:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        try:
            declared_size = int(content_length) if content_length else None
        except ValueError:
            declared_size = max_bytes + 1
        if declared_size is not None and declared_size > max_bytes:
            await self._reject(scope, receive, send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    raise RequestTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "The upload request is too large."},
        )
        await response(scope, receive, send)


app = FastAPI(title="OwlCam animal identifier", version=MODEL_VERSION)
app.add_middleware(
    BodyLimitMiddleware,
    max_bytes=MAX_REQUEST_BYTES,
    feedback_max_bytes=MAX_FEEDBACK_BYTES,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

jobs = JobStore()
feedback = FeedbackStore(DATA_DIR / "feedback.sqlite")
_hits: dict[str, deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="animal-id")
_inference_slot = threading.BoundedSemaphore(1)


class FeedbackBody(BaseModel):
    file_name: str | None = Field(default=None, max_length=255)
    classification: str | None = Field(default=None, max_length=120)
    looks_right: bool
    correction: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    i_dont_know: bool = False
    train_opt_in: bool = False
    model_version: str | None = Field(default=None, max_length=120)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    with _hits_lock:
        bucket = _hits[ip]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Please wait before identifying more photos.",
            )
        bucket.append(now)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/api/animal-identification/species")
def species_list() -> dict[str, list[str]]:
    return {"species": [name for name in load_species() if name != "unknown animal"]}


def _failure(file_name: str) -> ImageResult:
    return ImageResult(file_name=file_name, error=FAILURE, model_version=MODEL_VERSION)


def _oversized(file_name: str) -> ImageResult:
    return ImageResult(
        file_name=file_name,
        error="That photo is larger than 10 MB.",
        model_version=MODEL_VERSION,
    )


def _identify_with_timeout(files: list[tuple[str, bytes]]) -> list[ImageResult]:
    if not _inference_slot.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="The photo-processing server is busy. Please try again shortly.",
        )

    release_when_done = None
    results: list[ImageResult] = []
    try:
        for position, item in enumerate(files):
            future = _pool.submit(identify_images, [item])
            try:
                identified = future.result(timeout=INFERENCE_TIMEOUT_SECONDS)
            except FuturesTimeout:
                release_when_done = future
                results.append(_failure(item[0]))
                results.extend(
                    _failure(name) for name, _payload in files[position + 1 :]
                )
                break
            except Exception:
                results.append(_failure(item[0]))
            else:
                results.append(identified[0] if identified else _failure(item[0]))
    finally:
        if release_when_done is None:
            _inference_slot.release()
        else:
            release_when_done.add_done_callback(lambda _future: _inference_slot.release())
    return results


@app.post("/api/animal-identification")
async def identify(request: Request, images: list[UploadFile] = File(default=[])):
    _rate_limit(request)
    uploads = images or []
    if not uploads:
        raise HTTPException(status_code=400, detail="Add at least one photo.")
    if len(uploads) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail="You can send up to 5 photos at a time.")

    files: list[tuple[str, bytes]] = []
    valid_positions: list[int] = []
    results_by_position: dict[int, ImageResult] = {}
    for position, upload in enumerate(uploads):
        name = Path(upload.filename or "upload.jpg").name
        if upload.size is not None and upload.size > MAX_FILE_BYTES:
            results_by_position[position] = _oversized(name)
            await upload.close()
            continue
        payload = await upload.read(MAX_FILE_BYTES + 1)
        await upload.close()
        if len(payload) > MAX_FILE_BYTES:
            results_by_position[position] = _oversized(name)
            continue
        valid_positions.append(position)
        files.append((name, payload))

    if files:
        identified = await run_in_threadpool(_identify_with_timeout, files)
    else:
        identified = []
    results_by_position.update(zip(valid_positions, identified, strict=True))
    results = [results_by_position[position] for position in range(len(uploads))]

    stored: dict[int, bytes] = {}
    for index, result in enumerate(results, start=1):
        if result.annotated_jpeg:
            stored[index] = result.annotated_jpeg
        if result.error is None and not result.annotated_jpeg:
            result.error = FAILURE
    job_id = jobs.put(stored) if stored else uuid.uuid4().hex

    payload = []
    for index, result in enumerate(results, start=1):
        url = None
        if index in stored:
            url = f"/api/animal-identification/jobs/{job_id}/images/{index}"
        item = result.public_dict(annotated_image_url=url)
        item["unknown_threshold"] = UNKNOWN_THRESHOLD
        if result.error:
            item["error"] = result.error
        payload.append(item)
    return {"results": payload, "job_id": job_id, "model_version": MODEL_VERSION}


@app.get("/api/animal-identification/jobs/{job_id}/images/{index}")
def job_image(job_id: str, index: int) -> Response:
    payload = jobs.get_image(job_id, index)
    if payload is None:
        raise HTTPException(status_code=404, detail="That preview is no longer available.")
    return Response(content=payload, media_type="image/jpeg")


@app.post("/api/animal-identification/feedback")
def save_feedback(request: Request, body: FeedbackBody) -> dict[str, str]:
    _rate_limit(request)
    correction = "I don't know" if body.i_dont_know else body.correction
    feedback.add(
        file_name=body.file_name,
        classification=body.classification,
        looks_right=body.looks_right,
        correction=correction,
        note=body.note,
        train_opt_in=body.train_opt_in,
        model_version=body.model_version or MODEL_VERSION,
    )
    return {"status": "saved"}


def run() -> None:
    import uvicorn

    uvicorn.run(
        "animal_identifier.server:app",
        host=BIND_HOST,
        port=BIND_PORT,
        reload=False,
    )
