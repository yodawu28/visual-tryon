"""
Reset local kiosk SQLite/runtime state for repeatable Swagger testing.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.seed_size_charts import DEFAULT_SEED_PATH, seed_size_charts


@dataclass(frozen=True)
class ResetTarget:
    path: Path
    kind: str
    exists: bool


def build_reset_plan(
    *,
    data_dir: Path,
    include_size_charts: bool = True,
    include_garments: bool = True,
    include_avatar_cache_index: bool = False,
    include_runtime_files: bool = False,
) -> list[ResetTarget]:
    data_dir = data_dir.resolve()
    targets: list[ResetTarget] = []

    if include_size_charts:
        targets.append(_target(data_dir / "size_charts" / "size_charts.sqlite3"))
    if include_garments:
        targets.append(_target(data_dir / "garments" / "garments.sqlite3"))
    if include_avatar_cache_index:
        targets.append(_target(data_dir / "avatar_cache" / "cache_index.sqlite3"))

    if include_runtime_files:
        targets.extend(
            [
                _target(data_dir / "garments" / "images", kind="directory_contents"),
                _target(
                    data_dir / "kiosk_sessions" / "sessions",
                    kind="directory_contents",
                ),
                _target(
                    data_dir / "kiosk_sessions" / "captures",
                    kind="directory_contents",
                ),
                _target(data_dir / "kiosk_tryons", kind="directory_contents"),
                _target(data_dir / "jobs" / "metadata", kind="directory_contents"),
            ]
        )

    return targets


def reset_kiosk_state(
    *,
    data_dir: Path = Path("data"),
    execute: bool = False,
    include_size_charts: bool = True,
    include_garments: bool = True,
    include_avatar_cache_index: bool = False,
    include_runtime_files: bool = False,
    seed_default_size_charts: bool = False,
    seed_path: Path = DEFAULT_SEED_PATH,
) -> dict[str, Any]:
    targets = build_reset_plan(
        data_dir=data_dir,
        include_size_charts=include_size_charts,
        include_garments=include_garments,
        include_avatar_cache_index=include_avatar_cache_index,
        include_runtime_files=include_runtime_files,
    )

    deleted: list[str] = []
    for target in targets:
        if not execute or not target.exists:
            continue
        if target.kind == "file":
            target.path.unlink()
            deleted.append(str(target.path))
        elif target.kind == "directory_contents":
            _delete_directory_contents(target.path)
            deleted.append(f"{target.path}/*")
        else:
            raise ValueError(f"Unsupported reset target kind: {target.kind}")

    seed_result: dict[str, Any] | None = None
    if seed_default_size_charts:
        if execute:
            seed_result = seed_size_charts(
                seed_path=seed_path,
                db_path=Path(data_dir) / "size_charts" / "size_charts.sqlite3",
            )
        else:
            seed_result = {
                "dry_run": True,
                "seed_path": str(seed_path),
                "message": "Add --execute to seed default size charts.",
            }

    return {
        "execute": execute,
        "data_dir": str(Path(data_dir).resolve()),
        "planned_targets": [
            {
                "path": str(target.path),
                "kind": target.kind,
                "exists": target.exists,
            }
            for target in targets
        ],
        "deleted_count": len(deleted),
        "deleted": deleted,
        "seed_default_size_charts": seed_result,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete selected state. Without this flag the command is dry-run.",
    )
    parser.add_argument(
        "--keep-size-charts",
        action="store_true",
        help="Do not reset data/size_charts/size_charts.sqlite3.",
    )
    parser.add_argument(
        "--keep-garments",
        action="store_true",
        help="Do not reset data/garments/garments.sqlite3.",
    )
    parser.add_argument(
        "--include-avatar-cache-index",
        action="store_true",
        help="Also reset data/avatar_cache/cache_index.sqlite3.",
    )
    parser.add_argument(
        "--include-runtime-files",
        action="store_true",
        help=(
            "Also clear local garment images, kiosk sessions/captures, "
            "generated kiosk try-ons, and local job metadata."
        ),
    )
    parser.add_argument(
        "--seed-default-size-charts",
        action="store_true",
        help="Seed default generic size charts after reset.",
    )
    parser.add_argument(
        "--seed-path",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Seed JSON path used with --seed-default-size-charts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = reset_kiosk_state(
        data_dir=args.data_dir,
        execute=args.execute,
        include_size_charts=not args.keep_size_charts,
        include_garments=not args.keep_garments,
        include_avatar_cache_index=args.include_avatar_cache_index,
        include_runtime_files=args.include_runtime_files,
        seed_default_size_charts=args.seed_default_size_charts,
        seed_path=args.seed_path,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _target(path: Path, *, kind: str = "file") -> ResetTarget:
    return ResetTarget(path=path.resolve(), kind=kind, exists=path.exists())


def _delete_directory_contents(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_dir():
        raise ValueError(f"Expected directory target: {path}")
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
