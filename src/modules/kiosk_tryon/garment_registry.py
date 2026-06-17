"""
SQLite-backed garment registry for kiosk deployments.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from PIL import Image

GarmentCategory = Literal["tops", "bottoms", "one_pieces", "full_outfit"]

_CATEGORY_VALUES = {"tops", "bottoms", "one_pieces", "full_outfit"}
_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


@dataclass(frozen=True)
class GarmentRecord:
    garment_id: str
    name: str | None
    category: GarmentCategory
    garment_type: str | None
    storage_provider: str
    storage_uri: str
    image_sha256: str
    mime_type: str
    size_bytes: int
    original_filename: str | None
    size_chart_id: str | None
    size_chart: list[dict[str, Any]]
    created_at: str
    updated_at: str


class GarmentRegistry:
    """
    Local garment registry.

    The database stores metadata and storage references only. Image bytes stay in
    the configured storage directory so the same schema can later point to S3.
    """

    GARMENT_PREFIX = "garment:v1:"

    def __init__(self, *, db_path: Path, image_dir: Path) -> None:
        self.db_path = db_path
        self.image_dir = image_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_garment(
        self,
        *,
        image_bytes: bytes,
        category: str,
        name: str | None = None,
        garment_type: str | None = None,
        original_filename: str | None = None,
        size_chart_id: str | None = None,
        size_chart: list[dict[str, Any]] | None = None,
        max_size_bytes: int | None = None,
    ) -> GarmentRecord:
        if not image_bytes:
            raise ValueError("garment image file must not be empty")
        if max_size_bytes is not None and len(image_bytes) > max_size_bytes:
            raise ValueError("garment image file exceeds the configured upload limit")

        normalized_category = _normalize_category(category)
        normalized_size_chart = _normalize_size_chart(size_chart or [])
        mime_type, extension = _detect_image_type(image_bytes)
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
        now = _utc_now()
        garment_id = f"{self.GARMENT_PREFIX}{uuid4().hex}"
        image_path = self.image_dir / f"{_safe_filename(garment_id)}{extension}"
        image_path.write_bytes(image_bytes)

        record = GarmentRecord(
            garment_id=garment_id,
            name=_clean_optional_text(name),
            category=normalized_category,
            garment_type=_clean_optional_text(garment_type),
            storage_provider="local",
            storage_uri=str(image_path),
            image_sha256=image_sha256,
            mime_type=mime_type,
            size_bytes=len(image_bytes),
            original_filename=_clean_optional_text(original_filename),
            size_chart_id=_clean_optional_text(size_chart_id),
            size_chart=normalized_size_chart,
            created_at=now,
            updated_at=now,
        )
        self._insert_record(record)
        return record

    def get_garment(self, garment_id: str) -> GarmentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM garments WHERE garment_id = ?",
                (garment_id,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def list_garments(self, *, limit: int = 100) -> list[GarmentRecord]:
        bounded_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM garments
                ORDER BY created_at DESC, garment_id DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def exists(self, garment_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM garments WHERE garment_id = ?",
                (garment_id,),
            ).fetchone()
        return row is not None

    def read_image(self, garment_id: str) -> bytes:
        record = self.get_garment(garment_id)
        if record is None:
            raise FileNotFoundError(f"Garment not found: {garment_id}")
        if record.storage_provider != "local":
            raise ValueError(
                f"Unsupported garment storage provider: {record.storage_provider}"
            )

        image_path = Path(record.storage_uri)
        if not image_path.exists():
            raise FileNotFoundError(f"Garment image file not found: {garment_id}")
        return image_path.read_bytes()

    def _insert_record(self, record: GarmentRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO garments (
                    garment_id,
                    name,
                    category,
                    garment_type,
                    storage_provider,
                    storage_uri,
                    image_sha256,
                    mime_type,
                    size_bytes,
                    original_filename,
                    size_chart_id,
                    size_chart_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.garment_id,
                    record.name,
                    record.category,
                    record.garment_type,
                    record.storage_provider,
                    record.storage_uri,
                    record.image_sha256,
                    record.mime_type,
                    record.size_bytes,
                    record.original_filename,
                    record.size_chart_id,
                    json.dumps(record.size_chart, sort_keys=True),
                    record.created_at,
                    record.updated_at,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS garments (
                    garment_id TEXT PRIMARY KEY,
                    name TEXT,
                    category TEXT NOT NULL,
                    garment_type TEXT,
                    storage_provider TEXT NOT NULL,
                    storage_uri TEXT NOT NULL,
                    image_sha256 TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    original_filename TEXT,
                    size_chart_id TEXT,
                    size_chart_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(garments)").fetchall()
            }
            if "size_chart_json" not in columns:
                conn.execute(
                    "ALTER TABLE garments ADD COLUMN size_chart_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "size_chart_id" not in columns:
                conn.execute("ALTER TABLE garments ADD COLUMN size_chart_id TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_garments_category_created
                ON garments(category, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_garments_image_sha256
                ON garments(image_sha256)
                """
            )


def _record_from_row(row: sqlite3.Row) -> GarmentRecord:
    return GarmentRecord(
        garment_id=str(row["garment_id"]),
        name=row["name"],
        category=_normalize_category(str(row["category"])),
        garment_type=row["garment_type"],
        storage_provider=str(row["storage_provider"]),
        storage_uri=str(row["storage_uri"]),
        image_sha256=str(row["image_sha256"]),
        mime_type=str(row["mime_type"]),
        size_bytes=int(row["size_bytes"]),
        original_filename=row["original_filename"],
        size_chart_id=row["size_chart_id"],
        size_chart=_load_size_chart_json(str(row["size_chart_json"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _detect_image_type(image_bytes: bytes) -> tuple[str, str]:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            image_format = image.format
    except Exception as exc:
        raise ValueError(
            "garment image file must be a valid PNG, JPEG, or WEBP"
        ) from exc

    if image_format not in _IMAGE_FORMATS:
        raise ValueError("garment image file must be a PNG, JPEG, or WEBP image")
    return _IMAGE_FORMATS[image_format]


def _normalize_category(category: str) -> GarmentCategory:
    normalized = category.strip().lower()
    if normalized not in _CATEGORY_VALUES:
        supported = ", ".join(sorted(_CATEGORY_VALUES))
        raise ValueError(f"category must be one of: {supported}")
    return normalized  # type: ignore[return-value]


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_size_chart(size_chart: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    supported_measurements = {
        "chest_cm",
        "waist_cm",
        "hip_cm",
        "shoulder_cm",
        "length_cm",
        "inseam_cm",
    }
    for item in size_chart:
        if not isinstance(item, dict):
            raise ValueError("size_chart entries must be objects")
        size = item.get("size")
        if not isinstance(size, str) or not size.strip():
            raise ValueError("size_chart entries require a non-empty size")
        normalized_item: dict[str, Any] = {"size": size.strip()}
        for key in sorted(supported_measurements):
            if key not in item or item[key] is None:
                continue
            try:
                value = float(item[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"size_chart.{key} must be a positive number") from exc
            if value <= 0:
                raise ValueError(f"size_chart.{key} must be a positive number")
            normalized_item[key] = value
        normalized.append(normalized_item)
    return normalized


def parse_size_chart_json(size_chart_json: str | None) -> list[dict[str, Any]]:
    if size_chart_json is None or not size_chart_json.strip():
        return []
    try:
        payload = json.loads(size_chart_json)
    except json.JSONDecodeError as exc:
        raise ValueError("size_chart_json must be valid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("size_chart_json must be a JSON array")
    return _normalize_size_chart(payload)


def _load_size_chart_json(size_chart_json: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(size_chart_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    try:
        return _normalize_size_chart(payload)
    except ValueError:
        return []


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "-" for char in value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
