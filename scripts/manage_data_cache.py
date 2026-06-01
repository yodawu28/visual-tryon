"""
Inspect and prune local data/cache artifacts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PruneEntry:
    path: Path
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class PrunePlan:
    cache_dir: Path
    older_than_days: int
    entries: list[PruneEntry]


def collect_data_summary(data_dir: Path) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    top_level: dict[str, dict[str, int]] = {}
    total_files = 0
    total_size_bytes = 0

    if not data_dir.exists():
        return {
            "data_dir": str(data_dir),
            "total_files": 0,
            "total_size_bytes": 0,
            "top_level": {},
        }

    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        total_files += 1
        size_bytes = path.stat().st_size
        total_size_bytes += size_bytes
        relative = path.relative_to(data_dir)
        bucket = relative.parts[0] if relative.parts else "."
        top_level.setdefault(bucket, {"file_count": 0, "size_bytes": 0})
        top_level[bucket]["file_count"] += 1
        top_level[bucket]["size_bytes"] += size_bytes

    return {
        "data_dir": str(data_dir),
        "total_files": total_files,
        "total_size_bytes": total_size_bytes,
        "top_level": dict(sorted(top_level.items())),
    }


def build_prune_plan(
    cache_dir: Path,
    *,
    older_than_days: int,
    now: datetime | None = None,
) -> PrunePlan:
    cache_dir = cache_dir.resolve()
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=older_than_days)
    entries: list[PruneEntry] = []
    if not cache_dir.exists():
        return PrunePlan(
            cache_dir=cache_dir,
            older_than_days=older_than_days,
            entries=[],
        )

    for path in sorted(cache_dir.rglob("*")):
        if not path.is_file() or path.name == "cache_index.sqlite3":
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".json"}:
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if modified_at > cutoff:
            continue
        entries.append(
            PruneEntry(
                path=path,
                size_bytes=path.stat().st_size,
                modified_at=modified_at.isoformat(),
            )
        )

    return PrunePlan(
        cache_dir=cache_dir,
        older_than_days=older_than_days,
        entries=entries,
    )


def prune_cache_files(plan: PrunePlan, *, execute: bool) -> dict[str, Any]:
    deleted_count = 0
    deleted_size_bytes = 0
    for entry in plan.entries:
        if not execute:
            continue
        if entry.path.exists():
            deleted_size_bytes += entry.path.stat().st_size
            entry.path.unlink()
            deleted_count += 1

    return {
        "cache_dir": str(plan.cache_dir),
        "older_than_days": plan.older_than_days,
        "execute": execute,
        "planned_count": len(plan.entries),
        "planned_size_bytes": sum(entry.size_bytes for entry in plan.entries),
        "deleted_count": deleted_count,
        "deleted_size_bytes": deleted_size_bytes,
        "entries": [
            {
                "path": str(entry.path),
                "size_bytes": entry.size_bytes,
                "modified_at": entry.modified_at,
            }
            for entry in plan.entries
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/avatar_cache"))
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--older-than-days", type=int, default=14)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete files selected by --prune. Without this flag prune is dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload: dict[str, Any] = {}
    if args.summary or not args.prune:
        payload["summary"] = collect_data_summary(args.data_dir)
    if args.prune:
        plan = build_prune_plan(
            args.cache_dir,
            older_than_days=args.older_than_days,
        )
        payload["prune"] = prune_cache_files(plan, execute=args.execute)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
