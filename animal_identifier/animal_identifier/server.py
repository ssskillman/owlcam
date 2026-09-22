from __future__ import annotations

import hmac
import logging
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from animal_identifier.alerts import maybe_send_species_alert
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
    VISIT_DEDUPE_SECONDS,
    VISIT_ADMIN_SECRET,
    VISIT_LIST_DEFAULT_LIMIT,
    VISIT_LOG_UNKNOWN,
)
from animal_identifier.pipeline import identify_images, load_species, load_taxonomy
from animal_identifier.schemas import ImageResult
from animal_identifier.store import (
    AlertCooldownStore,
    FeedbackStore,
    IdentificationStore,
    JobStore,
    VisitStore,
)

FAILURE = "We couldn't analyze this photo right now. Please try again in a moment."
DATA_DIR = Path(
    os.environ.get(
        "ANIMAL_ID_DATA_DIR",
        str(Path.home() / ".owlcam" / "animal-id"),
    )
)
MAX_REQUEST_BYTES = MAX_IMAGES * MAX_FILE_BYTES + 1_000_000
MAX_FEEDBACK_BYTES = 16 * 1024
logger = logging.getLogger(__name__)


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


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    # OAS 3.1 emits contentMediaType for files; Swagger UI then treats a list
    # of uploads as array<string>. 3.0 + format:binary restores the file picker.
    schema["openapi"] = "3.0.2"
    body = schema.get("components", {}).get("schemas", {}).get(
        "Body_identify_api_animal_identification_post"
    )
    if body:
        items = body["properties"]["images"]["items"]
        items["format"] = "binary"
        items.pop("contentMediaType", None)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

jobs = JobStore()
feedback = FeedbackStore(DATA_DIR / "feedback.sqlite")
identifications = IdentificationStore(DATA_DIR / "identifications.sqlite")
visits = VisitStore(DATA_DIR / "visits.sqlite", DATA_DIR / "visit-thumbnails")
alert_cooldowns = AlertCooldownStore(DATA_DIR / "alert-cooldowns.sqlite")
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


class SummarySpecies(BaseModel):
    species: str
    count: int


class SummaryCategory(BaseModel):
    category: str
    count: int
    species: list[SummarySpecies]


class IdentificationSummary(BaseModel):
    total: int
    categories: list[SummaryCategory]


class VisitItem(BaseModel):
    id: int
    created_at: str
    species: str
    category: str
    confidence: float
    is_unknown: bool
    model_version: str
    source: str
    thumbnail_url: str | None = None


class VisitList(BaseModel):
    visits: list[VisitItem]


class VisitStats(BaseModel):
    count: int
    hours: int
    source: str | None = None


class VisitCalendarDay(BaseModel):
    date: str
    visits: int
    entrances: int
    exits: int
    pics: int


class VisitCalendar(BaseModel):
    year: int
    month: int
    days: list[VisitCalendarDay]


class VisitDayEvent(BaseModel):
    time: str
    kind: str
    species: str
    category: str
    confidence: float | None = None
    visit_id: int | None = None
    has_photo: bool = False
    thumbnail_url: str | None = None


class VisitDayActivity(BaseModel):
    date: str
    events: list[VisitDayEvent]


def _request_source(request: Request) -> str:
    header = (request.headers.get("x-owlcam-source") or "").strip()
    return header or "browser"


def _record_visit(
    *,
    result: ImageResult,
    source: str,
    original_bytes: bytes | None,
) -> None:
    if result.error is not None:
        return
    if result.is_unknown and not VISIT_LOG_UNKNOWN:
        return
    taxonomy = load_taxonomy()
    category = taxonomy.get(result.classification, "unknown")
    if (
        not result.is_unknown
        and source == "feed_watcher"
        and visits.recent_same_species(
            result.classification,
            source,
            VISIT_DEDUPE_SECONDS,
        )
    ):
        return
    thumb = result.annotated_jpeg or original_bytes
    visit_id = visits.add(
        species=result.classification,
        category=category,
        confidence=result.confidence,
        is_unknown=result.is_unknown,
        model_version=result.model_version or MODEL_VERSION,
        source=source,
        thumbnail=thumb,
    )
    if visit_id and not result.is_unknown:
        maybe_send_species_alert(
            species=result.classification,
            confidence=result.confidence,
            source=source,
            cooldowns=alert_cooldowns,
        )


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


@app.get(
    "/api/animal-identification/summary",
    response_model=IdentificationSummary,
)
def identification_summary() -> dict:
    return identifications.summary()


@app.get(
    "/api/animal-identification/visits/stats",
    response_model=VisitStats,
)
def visit_stats(
    hours: int = 24,
    source: str | None = "feed_watcher",
) -> dict:
    capped_hours = max(1, min(hours, 168))
    normalized_source = source.strip() if source else None
    if normalized_source == "":
        normalized_source = None
    count = visits.count_since_hours(
        capped_hours,
        source=normalized_source,
        require_thumbnail=True,
    )
    return {
        "count": count,
        "hours": capped_hours,
        "source": normalized_source,
    }


@app.get(
    "/api/animal-identification/visits/calendar",
    response_model=VisitCalendar,
)
def visit_calendar(
    year: int,
    month: int,
    source: str | None = "feed_watcher",
) -> dict:
    capped_year = max(2020, min(year, 2100))
    capped_month = max(1, min(month, 12))
    normalized_source = source.strip() if source else None
    if normalized_source == "":
        normalized_source = None
    days = visits.month_calendar(
        capped_year,
        capped_month,
        source=normalized_source,
    )
    return {
        "year": capped_year,
        "month": capped_month,
        "days": days,
    }


@app.get(
    "/api/animal-identification/visits/day",
    response_model=VisitDayActivity,
)
def visit_day_activity(
    date: str,
    source: str | None = "feed_watcher",
) -> dict:
    if len(date) != 10 or date[4] != "-" or date[7] != "-":
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD")
    normalized_source = source.strip() if source else None
    if normalized_source == "":
        normalized_source = None
    raw_events = visits.day_activity(date, source=normalized_source)
    events = []
    for row in raw_events:
        thumb_url = None
        visit_id = row.get("visit_id")
        if row.get("has_photo") and visit_id:
            thumb_url = f"/api/animal-identification/visits/{visit_id}/thumbnail"
        events.append(
            VisitDayEvent(
                time=str(row["time"]),
                kind=str(row["kind"]),
                species=str(row["species"]),
                category=str(row["category"]),
                confidence=row["confidence"],
                visit_id=visit_id,
                has_photo=bool(row.get("has_photo")),
                thumbnail_url=thumb_url,
            )
        )
    return {"date": date, "events": events}


@app.get(
    "/api/animal-identification/visits",
    response_model=VisitList,
)
def list_visits(
    limit: int = VISIT_LIST_DEFAULT_LIMIT,
    species: str | None = None,
) -> dict:
    capped = max(1, min(limit, 200))
    rows = visits.list_visits(limit=capped, species=species)
    payload = []
    for row in rows:
        thumb_url = None
        if row.thumbnail_name:
            thumb_url = f"/api/animal-identification/visits/{row.id}/thumbnail"
        payload.append(
            VisitItem(
                id=row.id,
                created_at=row.created_at,
                species=row.species,
                category=row.category,
                confidence=row.confidence,
                is_unknown=row.is_unknown,
                model_version=row.model_version,
                source=row.source,
                thumbnail_url=thumb_url,
            )
        )
    return {"visits": payload}


@app.delete("/api/animal-identification/visits/{visit_id}")
def delete_visit(visit_id: int, request: Request) -> dict[str, object]:
    if not VISIT_ADMIN_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Visit deletion is not configured on this server.",
        )
    provided = request.headers.get("X-OwlCam-Visit-Admin", "")
    if not hmac.compare_digest(provided, VISIT_ADMIN_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    if visit_id < 1:
        raise HTTPException(status_code=422, detail="Invalid visit id")
    if not visits.delete_visit(visit_id):
        raise HTTPException(status_code=404, detail="Visit not found")
    return {"deleted": True, "id": visit_id}


@app.get("/api/animal-identification/visits/{visit_id}/thumbnail")
def visit_thumbnail(visit_id: int) -> Response:
    row = visits.get_visit(visit_id)
    if row is None or not row.thumbnail_name:
        raise HTTPException(status_code=404, detail="That thumbnail is not available.")
    path = visits.thumbnail_path(row.thumbnail_name)
    if path is None:
        raise HTTPException(status_code=404, detail="That thumbnail is not available.")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


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

    source = _request_source(request)
    files: list[tuple[str, bytes]] = []
    payloads_by_position: dict[int, bytes] = {}
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
        payloads_by_position[position] = payload

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

    taxonomy = load_taxonomy()
    history_rows = [
        (
            result.classification,
            taxonomy[result.classification],
            result.model_version or MODEL_VERSION,
        )
        for result in results
        if result.error is None
        and not result.is_unknown
        and result.classification in taxonomy
    ]
    try:
        identifications.add_many(history_rows)
    except sqlite3.Error:
        # Anonymous history is optional; never discard a completed inference
        # because the aggregate database is briefly locked or unavailable.
        logger.exception("Could not record identification summary")

    for position, result in results_by_position.items():
        try:
            _record_visit(
                result=result,
                source=source,
                original_bytes=payloads_by_position.get(position),
            )
        except sqlite3.Error:
            logger.exception("Could not record visit log entry")

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
