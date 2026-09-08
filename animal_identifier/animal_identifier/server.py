from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from animal_identifier.config import (
    BIND_HOST,
    BIND_PORT,
    CORS_ORIGINS,
    INFERENCE_TIMEOUT_SECONDS,
    MAX_IMAGES,
    MODEL_VERSION,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from animal_identifier.pipeline import identify_images, load_species
from animal_identifier.store import FeedbackStore, JobStore

FAILURE = "We couldn't analyze this photo right now. Please try again in a moment."
DATA_DIR = Path(os.environ.get("ANIMAL_ID_DATA_DIR", str(Path.home() / ".owlcam" / "animal-id")))

app = FastAPI(title="OwlCam animal identifier", version=MODEL_VERSION)
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
_hits_lock = __import__("threading").Lock()
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="animal-id")


class FeedbackBody(BaseModel):
    file_name: str | None = None
    classification: str | None = None
    looks_right: bool
    correction: str | None = None
    note: str | None = None
    i_dont_know: bool = False
    train_opt_in: bool = False
    model_version: str | None = None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    with _hits_lock:
        bucket = _hits[ip]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(status_code=429, detail="Please wait before identifying more photos.")
        bucket.append(now)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/api/animal-identification/species")
def species_list() -> dict[str, list[str]]:
    return {"species": [name for name in load_species() if name != "unknown animal"]}


@app.post("/api/animal-identification")
async def identify(request: Request, images: list[UploadFile] = File(default=[])):
    _rate_limit(request)
    uploads = images or []
    if not uploads:
        raise HTTPException(status_code=400, detail="Add at least one photo.")
    if len(uploads) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail="You can send up to 5 photos at a time.")

    files: list[tuple[str, bytes]] = []
    for upload in uploads:
        payload = await upload.read()
        name = Path(upload.filename or "upload.jpg").name
        files.append((name, payload))

    future = _pool.submit(identify_images, files)
    try:
        results = future.result(timeout=INFERENCE_TIMEOUT_SECONDS)
    except FuturesTimeout as exc:
        future.cancel()
        raise HTTPException(status_code=504, detail=FAILURE) from exc

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
def save_feedback(body: FeedbackBody) -> dict[str, str]:
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
