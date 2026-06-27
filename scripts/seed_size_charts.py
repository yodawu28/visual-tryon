"""
Seed reusable kiosk size charts into the local SQLite catalog.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.kiosk_tryon.size_chart_seeding import (
    DEFAULT_SIZE_CHART_SEED_PATH,
    load_seed_payload as load_seed_payload,
    seed_size_charts as _seed_size_charts,
)


DEFAULT_SEED_PATH = DEFAULT_SIZE_CHART_SEED_PATH
DEFAULT_DB_PATH = Path("data/size_charts/size_charts.sqlite3")


def seed_size_charts(
    *,
    seed_path: Path = DEFAULT_SEED_PATH,
    db_path: Path = DEFAULT_DB_PATH,
    dry_run: bool = False,
) -> dict[str, object]:
    return _seed_size_charts(seed_path=seed_path, db_path=db_path, dry_run=dry_run)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-path",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Path to a seed JSON file with a size_charts array.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite size chart catalog path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report changes without creating records.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = seed_size_charts(
        seed_path=args.seed_path,
        db_path=args.db_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
