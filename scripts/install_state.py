"""Track dependency install state for idempotent RunPod setup."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_VERSION = 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "write"))
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--value", action="append", default=[])
    parser.add_argument("--exists", action="append", default=[])
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    state_file = state_dir / f"{_safe_name(args.name)}.json"
    payload = _build_payload(
        name=args.name,
        paths=[Path(path) for path in args.path],
        values=list(args.value),
        exists=[Path(path) for path in args.exists],
    )

    if args.command == "check":
        if not _exists_paths_ready(payload):
            print(f"{args.name}: required path missing")
            return 1
        if not state_file.exists():
            print(f"{args.name}: install state missing")
            return 1
        try:
            previous = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"{args.name}: install state is invalid")
            return 1
        if previous.get("signature") != payload["signature"]:
            print(f"{args.name}: install state changed")
            return 1
        print(f"{args.name}: install state ready")
        return 0

    state_dir.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                **payload,
                "written_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{args.name}: install state written")
    return 0


def _build_payload(
    *,
    name: str,
    paths: list[Path],
    values: list[str],
    exists: list[Path],
) -> dict[str, Any]:
    inputs = {
        "version": STATE_VERSION,
        "name": name,
        "paths": [_path_fingerprint(path) for path in paths],
        "values": values,
        "exists": [str(path) for path in exists],
    }
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **inputs,
        "signature": hashlib.sha256(encoded).hexdigest(),
    }


def _path_fingerprint(path: Path) -> dict[str, str]:
    if not path.exists():
        return {
            "path": str(path),
            "sha256": "missing",
        }
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
    }


def _exists_paths_ready(payload: dict[str, Any]) -> bool:
    return all(Path(path).exists() for path in payload["exists"])


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")
    if not safe:
        raise ValueError("Install state name must contain at least one safe character")
    return safe


if __name__ == "__main__":
    raise SystemExit(main())
