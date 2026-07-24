"""
Seed local kiosk garments from a prepared image directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from src.modules.kiosk_tryon.garment_registry import GarmentRegistry
from src.modules.kiosk_tryon.size_chart_registry import SizeChartRegistry


DEFAULT_SOURCE_DIR = Path("data/garment_catalog")
DEFAULT_STORAGE_DIR = Path("data/garments")
DEFAULT_SIZE_CHART_DB_PATH = Path("data/size_charts/size_charts.sqlite3")
DEFAULT_CATEGORY = "tops"
DEFAULT_GARMENT_TYPE = "regular_top"
DEFAULT_SIZE_CHART_NAME = "VN Generic Adult Tops Regular"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def seed_garment_catalog(
    *,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    storage_dir: Path = DEFAULT_STORAGE_DIR,
    size_chart_db_path: Path | None = DEFAULT_SIZE_CHART_DB_PATH,
    dry_run: bool = False,
) -> dict[str, Any]:
    source_paths = _list_source_images(source_dir)
    registry = GarmentRegistry(
        db_path=storage_dir / "garments.sqlite3",
        image_dir=storage_dir / "images",
    )
    size_chart_id = _find_default_size_chart_id(size_chart_db_path)
    existing_hashes = {
        record.image_sha256: record
        for record in registry.list_garments(limit=500)
    }
    created: list[str] = []
    skipped: list[str] = []

    for source_path in source_paths:
        image_bytes = source_path.read_bytes()
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
        existing = existing_hashes.get(image_sha256)
        if existing is not None:
            skipped.append(existing.garment_id)
            continue
        if dry_run:
            created.append(f"dry-run:{source_path.name}")
            continue
        record = registry.create_garment(
            image_bytes=image_bytes,
            category=DEFAULT_CATEGORY,
            name=_display_name(source_path),
            garment_type=DEFAULT_GARMENT_TYPE,
            original_filename=source_path.name,
            size_chart_id=size_chart_id,
        )
        existing_hashes[record.image_sha256] = record
        created.append(record.garment_id)

    return {
        "dry_run": dry_run,
        "source_dir": str(source_dir),
        "storage_dir": str(storage_dir),
        "size_chart_db_path": str(size_chart_db_path) if size_chart_db_path else None,
        "size_chart_id": size_chart_id,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing prepared garment images.",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=DEFAULT_STORAGE_DIR,
        help="Garment registry storage directory containing garments.sqlite3 and images/.",
    )
    parser.add_argument(
        "--size-chart-db-path",
        type=Path,
        default=DEFAULT_SIZE_CHART_DB_PATH,
        help="Optional SQLite size chart catalog path used to attach the default tops chart.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report changes without creating garment records.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = seed_garment_catalog(
        source_dir=args.source_dir,
        storage_dir=args.storage_dir,
        size_chart_db_path=args.size_chart_db_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _list_source_images(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Garment catalog source directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise ValueError(f"Garment catalog source must be a directory: {source_dir}")
    return sorted(
        path for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _find_default_size_chart_id(size_chart_db_path: Path | None) -> str | None:
    if size_chart_db_path is None:
        return None
    registry = SizeChartRegistry(db_path=size_chart_db_path)
    records = registry.list_size_charts(
        country_code="VN",
        category=DEFAULT_CATEGORY,
        limit=500,
    )
    for record in records:
        if record.name == DEFAULT_SIZE_CHART_NAME and record.garment_type == DEFAULT_GARMENT_TYPE:
            return record.size_chart_id
    return None


def _display_name(path: Path) -> str:
    match = re.search(r"(\d+)", path.stem)
    if match:
        return f"Default garment {match.group(1)}"
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or "Default garment"


if __name__ == "__main__":
    raise SystemExit(main())
