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


@dataclass(frozen=True)
class VisitRecord:
    id: int
    created_at: str
    species: str
    category: str
    confidence: float
    is_unknown: bool
    model_version: str
    source: str
    thumbnail_name: str | None


class VisitStore:
    """Timestamped visits with on-disk thumbnails for nest feed automation."""

    def __init__(self, db_path: Path, thumbnail_dir: Path) -> None:
        self.db_path = db_path
        self.thumbnail_dir = thumbnail_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    species TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    is_unknown INTEGER NOT NULL,
                    model_version TEXT NOT NULL,
                    source TEXT NOT NULL,
                    thumbnail_name TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS visits_created_at
                ON visits (created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS visits_species_created
                ON visits (species, created_at DESC)
                """
            )

    def recent_same_species(
        self,
        species: str,
        source: str,
        within_seconds: int,
    ) -> bool:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT 1 FROM visits
                WHERE species = ? AND source = ? AND is_unknown = 0
                  AND datetime(created_at) > datetime('now', ?)
                LIMIT 1
                """,
                (species, source, f"-{within_seconds} seconds"),
            ).fetchone()
        return row is not None

    def add(
        self,
        *,
        species: str,
        category: str,
        confidence: float,
        is_unknown: bool,
        model_version: str,
        source: str,
        thumbnail: bytes | None,
    ) -> int | None:
        thumb_name = None
        if thumbnail:
            thumb_name = f"{uuid.uuid4().hex}.jpg"
            (self.thumbnail_dir / thumb_name).write_bytes(thumbnail)
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO visits (
                    created_at, species, category, confidence, is_unknown,
                    model_version, source, thumbnail_name
                ) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    species,
                    category,
                    confidence,
                    int(is_unknown),
                    model_version,
                    source,
                    thumb_name,
                ),
            )
            return int(cursor.lastrowid)

    def get_visit(self, visit_id: int) -> VisitRecord | None:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT id, created_at, species, category, confidence, is_unknown,
                       model_version, source, thumbnail_name
                FROM visits WHERE id = ?
                """,
                (visit_id,),
            ).fetchone()
        if row is None:
            return None
        return VisitRecord(
            id=row[0],
            created_at=row[1],
            species=row[2],
            category=row[3],
            confidence=row[4],
            is_unknown=bool(row[5]),
            model_version=row[6],
            source=row[7],
            thumbnail_name=row[8],
        )

    def count_since_hours(
        self,
        hours: int,
        *,
        source: str | None = None,
        require_thumbnail: bool = True,
    ) -> int:
        query = """
            SELECT COUNT(*) FROM visits
            WHERE datetime(created_at) > datetime('now', ?)
        """
        params: list[object] = [f"-{hours} hours"]
        if source:
            query += " AND source = ?"
            params.append(source)
        if require_thumbnail:
            query += " AND thumbnail_name IS NOT NULL"
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(query, params).fetchone()
        return int(row[0]) if row else 0

    def list_visits(
        self,
        *,
        limit: int,
        species: str | None = None,
    ) -> list[VisitRecord]:
        query = """
            SELECT id, created_at, species, category, confidence, is_unknown,
                   model_version, source, thumbnail_name
            FROM visits
        """
        params: list[object] = []
        if species:
            query += " WHERE species = ?"
            params.append(species)
        query += " ORDER BY datetime(created_at) DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            VisitRecord(
                id=row[0],
                created_at=row[1],
                species=row[2],
                category=row[3],
                confidence=row[4],
                is_unknown=bool(row[5]),
                model_version=row[6],
                source=row[7],
                thumbnail_name=row[8],
            )
            for row in rows
        ]

    def thumbnail_path(self, thumbnail_name: str) -> Path | None:
        path = self.thumbnail_dir / thumbnail_name
        return path if path.is_file() else None

    def delete_visit(self, visit_id: int) -> bool:
        row = self.get_visit(visit_id)
        if row is None:
            return False
        if row.thumbnail_name:
            thumb = self.thumbnail_dir / row.thumbnail_name
            try:
                thumb.unlink(missing_ok=True)
            except OSError:
                pass
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM visits WHERE id = ?",
                (visit_id,),
            )
            return cursor.rowcount > 0


class AlertCooldownStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_cooldowns (
                    species TEXT PRIMARY KEY,
                    last_sent_at TEXT NOT NULL
                )
                """
            )

    def may_send(self, species: str, cooldown_seconds: int) -> bool:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT last_sent_at FROM alert_cooldowns WHERE species = ?
                """,
                (species,),
            ).fetchone()
        if row is None:
            return True
        with sqlite3.connect(self.path) as connection:
            recent = connection.execute(
                """
                SELECT 1 FROM alert_cooldowns
                WHERE species = ?
                  AND datetime(last_sent_at) > datetime('now', ?)
                """,
                (species, f"-{cooldown_seconds} seconds"),
            ).fetchone()
        return recent is None

    def mark_sent(self, species: str) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO alert_cooldowns (species, last_sent_at)
                VALUES (?, datetime('now'))
                ON CONFLICT(species) DO UPDATE SET last_sent_at = datetime('now')
                """,
                (species,),
            )
