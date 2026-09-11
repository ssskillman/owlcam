from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from animal_identifier.config import JOB_TTL_SECONDS


@dataclass
class StoredJob:
    job_id: str
    created_at: float
    images: dict[int, bytes] = field(default_factory=dict)


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, StoredJob] = {}

    def put(self, images: dict[int, bytes]) -> str:
        self.purge()
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = StoredJob(job_id=job_id, created_at=time.time(), images=images)
        return job_id

    def get_image(self, job_id: str, index: int) -> bytes | None:
        self.purge()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return job.images.get(index)

    def purge(self) -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        with self._lock:
            expired = [key for key, job in self._jobs.items() if job.created_at < cutoff]
            for key in expired:
                del self._jobs[key]


class FeedbackStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    file_name TEXT,
                    classification TEXT,
                    looks_right INTEGER NOT NULL,
                    correction TEXT,
                    note TEXT,
                    train_opt_in INTEGER NOT NULL DEFAULT 0,
                    model_version TEXT
                )
                """
            )

    def add(
        self,
        *,
        file_name: str | None,
        classification: str | None,
        looks_right: bool,
        correction: str | None,
        note: str | None,
        train_opt_in: bool,
        model_version: str | None,
    ) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO feedback (
                    created_at, file_name, classification, looks_right,
                    correction, note, train_opt_in, model_version
                ) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_name,
                    classification,
                    int(looks_right),
                    correction,
                    note,
                    int(train_opt_in),
                    model_version,
                ),
            )


class IdentificationStore:
    """Anonymous aggregate history; no image, filename, IP, or user identifier."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS identifications (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    species TEXT NOT NULL,
                    category TEXT NOT NULL,
                    model_version TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS identifications_category_species
                ON identifications (category, species)
                """
            )

    def add_many(self, rows: list[tuple[str, str, str]]) -> None:
        if not rows:
            return
        with sqlite3.connect(self.path) as connection:
            connection.executemany(
                """
                INSERT INTO identifications (
                    created_at, species, category, model_version
                ) VALUES (datetime('now'), ?, ?, ?)
                """,
                rows,
            )

    def summary(self) -> dict:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT category, species, COUNT(*) AS count
                FROM identifications
                GROUP BY category, species
                ORDER BY category, count DESC, species
                """
            ).fetchall()

        categories: dict[str, dict] = {}
        total = 0
        for category, species, count in rows:
            group = categories.setdefault(
                category,
                {"category": category, "count": 0, "species": []},
            )
            group["count"] += count
            group["species"].append({"species": species, "count": count})
            total += count
        ordered = sorted(
            categories.values(),
            key=lambda row: (-row["count"], row["category"]),
        )
        return {"total": total, "categories": ordered}
