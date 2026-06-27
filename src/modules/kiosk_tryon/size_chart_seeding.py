"""
Default size chart seeding utilities for kiosk deployments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.modules.kiosk_tryon.size_chart_registry import (
    SizeChartRecord,
    SizeChartRegistry,
)


DEFAULT_SIZE_CHART_SEED_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "seed_data"
    / "size_charts"
    / "default_size_charts.json"
)


def load_seed_payload(seed_path: Path) -> list[dict[str, Any]]:
    with seed_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("seed file must contain a JSON object")
    size_charts = payload.get("size_charts")
    if not isinstance(size_charts, list):
        raise ValueError("seed file must include a size_charts array")
    return [_validate_seed_entry(entry) for entry in size_charts]


def seed_size_charts(
    *,
    seed_path: Path,
    db_path: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    entries = load_seed_payload(seed_path)
    registry = SizeChartRegistry(db_path=db_path)
    created: list[str] = []
    skipped: list[str] = []

    for entry in entries:
        existing = _find_existing_size_chart(registry, entry)
        if existing is not None:
            skipped.append(existing.size_chart_id)
            continue
        if dry_run:
            created.append(f"dry-run:{entry['name']}")
            continue
        record = registry.create_size_chart(
            name=entry["name"],
            country_code=entry["country_code"],
            region=entry.get("region"),
            category=entry["category"],
            garment_type=entry.get("garment_type"),
            source_type=entry.get("source_type"),
            source_url=entry.get("source_url"),
            last_verified_at=entry.get("last_verified_at"),
            size_chart=entry["size_chart"],
            notes=entry.get("notes"),
        )
        created.append(record.size_chart_id)

    return {
        "dry_run": dry_run,
        "seed_path": str(seed_path),
        "db_path": str(db_path),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }


def seed_default_size_charts(*, db_path: Path, dry_run: bool = False) -> dict[str, Any]:
    return seed_size_charts(
        seed_path=DEFAULT_SIZE_CHART_SEED_PATH,
        db_path=db_path,
        dry_run=dry_run,
    )


def _find_existing_size_chart(
    registry: SizeChartRegistry,
    entry: dict[str, Any],
) -> SizeChartRecord | None:
    records = registry.list_size_charts(
        country_code=str(entry["country_code"]),
        category=str(entry["category"]),
        limit=500,
    )
    entry_name = str(entry["name"]).strip()
    entry_garment_type = _optional_string(entry.get("garment_type"))
    for record in records:
        if record.name != entry_name:
            continue
        if record.garment_type != entry_garment_type:
            continue
        return record
    return None


def _validate_seed_entry(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("size_charts entries must be objects")
    for field in ("name", "country_code", "category", "size_chart"):
        if field not in entry:
            raise ValueError(f"size chart seed entry requires {field}")
    if not isinstance(entry["size_chart"], list) or not entry["size_chart"]:
        raise ValueError("size chart seed entry requires non-empty size_chart")
    return entry


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None
