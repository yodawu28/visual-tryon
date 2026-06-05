"""
SQLite-backed size chart catalog for kiosk deployments.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.modules.kiosk_tryon.garment_registry import (
    GarmentCategory,
    _clean_optional_text,
    _normalize_category,
    _normalize_size_chart,
    _utc_now,
)


@dataclass(frozen=True)
class SizeChartRecord:
    size_chart_id: str
    name: str
    country_code: str
    region: str | None
    category: GarmentCategory
    garment_type: str | None
    source_type: str | None
    source_url: str | None
    last_verified_at: str | None
    size_chart: list[dict[str, Any]]
    notes: str | None
    created_at: str
    updated_at: str


class SizeChartRegistry:
    """
    Local size chart catalog.

    Size charts are mostly static market metadata, so garments should reference
    a chart by id instead of copying the same rows into every garment record.
    """

    SIZE_CHART_PREFIX = "size-chart:v1:"

    def __init__(self, *, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_size_chart(
        self,
        *,
        name: str,
        country_code: str,
        category: str,
        size_chart: list[dict[str, Any]],
        region: str | None = None,
        garment_type: str | None = None,
        source_type: str | None = None,
        source_url: str | None = None,
        last_verified_at: str | None = None,
        notes: str | None = None,
    ) -> SizeChartRecord:
        clean_name = _clean_optional_text(name)
        if clean_name is None:
            raise ValueError("name must not be empty")
        normalized_country_code = _normalize_country_code(country_code)
        normalized_category = _normalize_category(category)
        normalized_size_chart = _normalize_size_chart(size_chart)
        if not normalized_size_chart:
            raise ValueError("size_chart must include at least one size row")

        now = _utc_now()
        record = SizeChartRecord(
            size_chart_id=f"{self.SIZE_CHART_PREFIX}{uuid4().hex}",
            name=clean_name,
            country_code=normalized_country_code,
            region=_clean_optional_text(region),
            category=normalized_category,
            garment_type=_clean_optional_text(garment_type),
            source_type=_clean_optional_text(source_type),
            source_url=_clean_optional_text(source_url),
            last_verified_at=_clean_optional_text(last_verified_at),
            size_chart=normalized_size_chart,
            notes=_clean_optional_text(notes),
            created_at=now,
            updated_at=now,
        )
        self._insert_record(record)
        return record

    def get_size_chart(self, size_chart_id: str) -> SizeChartRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM size_charts WHERE size_chart_id = ?",
                (size_chart_id,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def list_size_charts(
        self,
        *,
        country_code: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[SizeChartRecord]:
        bounded_limit = max(1, min(limit, 500))
        filters: list[str] = []
        params: list[Any] = []
        if country_code:
            filters.append("country_code = ?")
            params.append(_normalize_country_code(country_code))
        if category:
            filters.append("category = ?")
            params.append(_normalize_category(category))

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(bounded_limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM size_charts
                {where_clause}
                ORDER BY country_code ASC, category ASC, created_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def _insert_record(self, record: SizeChartRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO size_charts (
                    size_chart_id,
                    name,
                    country_code,
                    region,
                    category,
                    garment_type,
                    source_type,
                    source_url,
                    last_verified_at,
                    size_chart_json,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.size_chart_id,
                    record.name,
                    record.country_code,
                    record.region,
                    record.category,
                    record.garment_type,
                    record.source_type,
                    record.source_url,
                    record.last_verified_at,
                    json.dumps(record.size_chart, sort_keys=True),
                    record.notes,
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
                CREATE TABLE IF NOT EXISTS size_charts (
                    size_chart_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    region TEXT,
                    category TEXT NOT NULL,
                    garment_type TEXT,
                    source_type TEXT,
                    source_url TEXT,
                    last_verified_at TEXT,
                    size_chart_json TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_size_charts_market_category
                ON size_charts(country_code, category, garment_type)
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(size_charts)").fetchall()
            }
            if "source_type" not in columns:
                conn.execute("ALTER TABLE size_charts ADD COLUMN source_type TEXT")
            if "source_url" not in columns:
                conn.execute("ALTER TABLE size_charts ADD COLUMN source_url TEXT")
            if "last_verified_at" not in columns:
                conn.execute(
                    "ALTER TABLE size_charts ADD COLUMN last_verified_at TEXT"
                )


def _record_from_row(row: sqlite3.Row) -> SizeChartRecord:
    return SizeChartRecord(
        size_chart_id=str(row["size_chart_id"]),
        name=str(row["name"]),
        country_code=str(row["country_code"]),
        region=row["region"],
        category=_normalize_category(str(row["category"])),
        garment_type=row["garment_type"],
        source_type=row["source_type"],
        source_url=row["source_url"],
        last_verified_at=row["last_verified_at"],
        size_chart=_load_size_chart_json(str(row["size_chart_json"])),
        notes=row["notes"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


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


def _normalize_country_code(country_code: str) -> str:
    normalized = country_code.strip().upper()
    if not normalized:
        raise ValueError("country_code must not be empty")
    if len(normalized) > 12:
        raise ValueError("country_code must be 12 characters or fewer")
    return normalized
