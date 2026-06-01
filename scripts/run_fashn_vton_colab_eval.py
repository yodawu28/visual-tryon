"""
Run avatar + garment eval cases against a local/Colab FASHN VTON command.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.modules.evaluation.avatar_harness import (
    AvatarEvalRunner,
    build_avatar_dry_run_plan,
    load_avatar_eval_cases,
)
from src.modules.evaluation.harness import PreviewModelConfig
from src.modules.image_generator.local_fashn_vton_generator import (
    LocalFashnVtonGenerator,
)


def _positive_int(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed_value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FASHN VTON local/Colab avatar evaluation cases",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to avatar eval manifest JSON",
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
        help="Print planned FASHN eval runs without calling the command",
    )
    parser.add_argument(
        "--command-template",
        default=None,
        help=(
            "Command template used to run FASHN VTON. Supports placeholders: "
            "{avatar_image}, {garment_image}, {output_image}, {category}, {prompt}, "
            "{size}. Defaults to FASHN_VTON_COMMAND."
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional working directory for the FASHN command",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=_positive_int,
        default=900,
        help="Maximum seconds to wait for each local FASHN command",
    )
    parser.add_argument(
        "--model-name",
        default=LocalFashnVtonGenerator.DEFAULT_MODEL,
        help="Model name recorded in the eval report",
    )
    parser.add_argument(
        "--run-id",
        default="fashn_vton_local",
        help="Run id recorded in output image filenames and report",
    )
    return parser.parse_args(argv)


def _default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("data/eval/reports") / f"fashn-vton-colab-eval-{timestamp}.json"


def _preview_config(*, run_id: str, model_name: str) -> PreviewModelConfig:
    return PreviewModelConfig(
        run_id=run_id,
        model=model_name,
        model_version=None,
        input_mapping=LocalFashnVtonGenerator.DEFAULT_INPUT_MAPPING,
        prompt_variant=LocalFashnVtonGenerator.DEFAULT_PROMPT_VERSION,
    )


def _validate_cases_have_avatar_images(cases) -> None:
    missing_case_ids = [
        eval_case.case_id for eval_case in cases if eval_case.avatar_image_path is None
    ]
    if missing_case_ids:
        raise ValueError(
            "FASHN VTON Colab eval requires avatar_image_path for each case. "
            f"Missing cases: {', '.join(missing_case_ids)}"
        )


def build_fashn_generator_from_args(
    args: argparse.Namespace,
) -> LocalFashnVtonGenerator:
    command_template = args.command_template or os.getenv("FASHN_VTON_COMMAND")
    return LocalFashnVtonGenerator(
        command_template=command_template,
        work_dir=args.work_dir,
        timeout_seconds=args.timeout_seconds,
        model=args.model_name,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = load_avatar_eval_cases(args.manifest)
    if args.limit_cases is not None:
        cases = cases[: args.limit_cases]

    preview_config = _preview_config(run_id=args.run_id, model_name=args.model_name)

    if args.dry_run:
        plan = build_avatar_dry_run_plan(cases, [preview_config])
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    _validate_cases_have_avatar_images(cases)
    report_path = args.report_path or _default_report_path()
    generator = build_fashn_generator_from_args(args)
    report = AvatarEvalRunner().run_cases_with_preview_generators(
        cases=cases,
        preview_generators=[(preview_config.run_id, generator)],
        report_path=report_path,
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"Report written to {report_path}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
