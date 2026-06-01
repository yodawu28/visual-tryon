"""
SQLite-backed index for avatar preview cache artifacts.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

CacheArtifactKind = Literal["avatar", "preview"]


@dataclass(frozen=True)
class CacheArtifactRecord:
    cache_key: str
    artifact_kind: CacheArtifactKind
    image_path: Path
    metadata_path: Path | None = None
    model: str | None = None
    prompt_version: str | None = None
    input_mapping: str | None = None
    image_sha256: str | None = None
    parent_cache_key: str | None = None
    size_bytes: int = 0
    created_at: str | None = None
    last_accessed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AvatarCacheRegistry:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def upsert_artifact(self, record: CacheArtifactRecord) -> None:
        now = _utc_now()
        created_at = record.created_at or now
        last_accessed_at = record.last_accessed_at or now
        size_bytes = _file_size(record.image_path)
        metadata_json = json.dumps(record.metadata, sort_keys=True)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM cache_artifacts WHERE cache_key = ?",
                (record.cache_key,),
            ).fetchone()
            if existing is not None:
                created_at = str(existing["created_at"])
            conn.execute(
                """
                INSERT INTO cache_artifacts (
                    cache_key,
                    artifact_kind,
                    image_path,
                    metadata_path,
                    model,
                    prompt_version,
                    input_mapping,
                    image_sha256,
                    parent_cache_key,
                    size_bytes,
                    created_at,
                    last_accessed_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    artifact_kind = excluded.artifact_kind,
                    image_path = excluded.image_path,
                    metadata_path = excluded.metadata_path,
                    model = excluded.model,
                    prompt_version = excluded.prompt_version,
                    input_mapping = excluded.input_mapping,
                    image_sha256 = excluded.image_sha256,
                    parent_cache_key = excluded.parent_cache_key,
                    size_bytes = excluded.size_bytes,
                    last_accessed_at = excluded.last_accessed_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record.cache_key,
                    record.artifact_kind,
                    str(record.image_path),
                    str(record.metadata_path) if record.metadata_path else None,
                    record.model,
                    record.prompt_version,
                    record.input_mapping,
                    record.image_sha256,
                    record.parent_cache_key,
                    size_bytes,
                    created_at,
                    last_accessed_at,
                    metadata_json,
                ),
            )

    def get_artifact(self, cache_key: str) -> CacheArtifactRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cache_artifacts WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def mark_accessed(self, cache_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE cache_artifacts
                SET last_accessed_at = ?
                WHERE cache_key = ?
                """,
                (_utc_now(), cache_key),
            )

    def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT artifact_kind, COUNT(*) AS count, SUM(size_bytes) AS size_bytes
                FROM cache_artifacts
                GROUP BY artifact_kind
                ORDER BY artifact_kind
                """
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) AS count, SUM(size_bytes) AS size_bytes FROM cache_artifacts"
            ).fetchone()

        by_kind = {
            str(row["artifact_kind"]): {
                "count": int(row["count"]),
                "size_bytes": int(row["size_bytes"] or 0),
            }
            for row in rows
        }
        return {
            "db_path": str(self.db_path),
            "total_count": int(total["count"] or 0),
            "total_size_bytes": int(total["size_bytes"] or 0),
            "by_kind": by_kind,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_artifacts (
                    cache_key TEXT PRIMARY KEY,
                    artifact_kind TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    metadata_path TEXT,
                    model TEXT,
                    prompt_version TEXT,
                    input_mapping TEXT,
                    image_sha256 TEXT,
                    parent_cache_key TEXT,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_artifacts_kind_accessed
                ON cache_artifacts(artifact_kind, last_accessed_at)
                """
            )


def _record_from_row(row: sqlite3.Row) -> CacheArtifactRecord:
    metadata_path = row["metadata_path"]
    return CacheArtifactRecord(
        cache_key=str(row["cache_key"]),
        artifact_kind=row["artifact_kind"],
        image_path=Path(str(row["image_path"])),
        metadata_path=Path(str(metadata_path)) if metadata_path else None,
        model=row["model"],
        prompt_version=row["prompt_version"],
        input_mapping=row["input_mapping"],
        image_sha256=row["image_sha256"],
        parent_cache_key=row["parent_cache_key"],
        size_bytes=int(row["size_bytes"]),
        created_at=str(row["created_at"]),
        last_accessed_at=str(row["last_accessed_at"]),
        metadata=json.loads(str(row["metadata_json"])),
    )


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
