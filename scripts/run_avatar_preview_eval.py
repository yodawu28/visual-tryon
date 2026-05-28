"""
Run repeatable avatar-based garment preview evaluation cases.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.config.settings import get_settings
from src.modules.evaluation.avatar_harness import (
    AvatarEvalRunner,
    build_avatar_dry_run_plan,
    load_avatar_eval_cases,
)
from src.modules.evaluation.harness import load_preview_model_configs
from scripts.run_vto_eval import (
    _positive_int,
    build_preview_generator_from_config,
    validate_preview_model_configs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run avatar preview evaluation cases",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to avatar eval manifest JSON",
    )
    parser.add_argument(
        "--model-matrix",
        type=Path,
        default=None,
        help="Path to preview model matrix JSON",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Path for JSON report output",
    )
    parser.add_argument(
        "--limit-cases",
        type=_positive_int,
        default=None,
        help="Maximum number of manifest cases to run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned avatar eval runs without calling model providers",
    )
    return parser.parse_args(argv)


def _default_report_path() -> Path:
    settings = get_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return settings.eval_report_dir / f"avatar-preview-eval-{timestamp}.json"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.model_matrix is None:
        raise ValueError("--model-matrix is required for avatar preview eval")

    cases = load_avatar_eval_cases(args.manifest)
    if args.limit_cases is not None:
        cases = cases[: args.limit_cases]

    preview_model_configs = load_preview_model_configs(args.model_matrix)
    if not preview_model_configs:
        raise ValueError("No enabled preview model configs found in model matrix")

    validate_preview_model_configs(preview_model_configs)

    if args.dry_run:
        plan = build_avatar_dry_run_plan(cases, preview_model_configs)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    report_path = args.report_path or _default_report_path()
    preview_generators = [
        (
            preview_config.run_id,
            build_preview_generator_from_config(preview_config),
        )
        for preview_config in preview_model_configs
    ]
    report = AvatarEvalRunner().run_cases_with_preview_generators(
        cases=cases,
        preview_generators=preview_generators,
        report_path=report_path,
    )

    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"Report written to {report_path}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
