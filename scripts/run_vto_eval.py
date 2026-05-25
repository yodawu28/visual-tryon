"""
Run repeatable virtual try-on evaluation cases.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.settings import get_settings
from src.modules.evaluation.harness import (
    EvalCase,
    EvalRunner,
    PreviewModelConfig,
    load_eval_cases,
    load_preview_model_configs,
)
from src.modules.image_generator.replicate_preview_generator import (
    ReplicatePreviewGenerator,
)
from src.modules.semantic_parser.openai_client import SemanticParserClient

SUPPORTED_PREVIEW_INPUT_MAPPINGS = {
    "multi_image_edit",
    "google_nano_banana",
}
SUPPORTED_PREVIEW_PROMPT_VARIANTS = set(
    ReplicatePreviewGenerator.PREVIEW_PROMPT_VARIANTS
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
    parser = argparse.ArgumentParser(description="Run VTO evaluation cases")
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to eval manifest JSON",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Path for JSON report output",
    )
    parser.add_argument(
        "--model-matrix",
        type=Path,
        default=None,
        help="Path to preview model matrix JSON",
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
        help="Print planned eval runs without calling model providers",
    )
    return parser.parse_args(argv)


def _default_report_path() -> Path:
    settings = get_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return settings.eval_report_dir / f"vto-eval-{timestamp}.json"


def build_dry_run_plan(
    *,
    cases: list[EvalCase],
    preview_model_configs: list[PreviewModelConfig],
) -> dict[str, Any]:
    planned_runs = [
        {
            "case_id": eval_case.case_id,
            "run_id": preview_config.run_id,
            "model": preview_config.model,
            "input_mapping": preview_config.input_mapping,
            "prompt_variant": preview_config.prompt_variant,
        }
        for eval_case in cases
        for preview_config in preview_model_configs
    ]
    return {
        "summary": {
            "total_cases": len(cases),
            "preview_runs_per_case": len(preview_model_configs),
            "total_preview_runs": len(planned_runs),
        },
        "planned_runs": planned_runs,
    }


def build_preview_generator_from_config(
    preview_config: PreviewModelConfig,
    *,
    generator_factory: Callable[
        [],
        ReplicatePreviewGenerator,
    ] = ReplicatePreviewGenerator,
) -> ReplicatePreviewGenerator:
    generator = generator_factory()
    generator.model = preview_config.model
    generator.model_version = preview_config.model_version
    generator.input_mapping = preview_config.input_mapping
    generator.prompt_variant = preview_config.prompt_variant
    return generator


def _validate_preview_model_configs(
    preview_model_configs: list[PreviewModelConfig],
) -> None:
    unsupported_input_mappings = sorted(
        {
            preview_config.input_mapping
            for preview_config in preview_model_configs
            if preview_config.input_mapping not in SUPPORTED_PREVIEW_INPUT_MAPPINGS
        }
    )
    if unsupported_input_mappings:
        raise ValueError(
            "Unsupported preview input_mapping values: "
            f"{', '.join(unsupported_input_mappings)}"
        )

    unsupported_prompt_variants = sorted(
        {
            preview_config.prompt_variant
            for preview_config in preview_model_configs
            if preview_config.prompt_variant not in SUPPORTED_PREVIEW_PROMPT_VARIANTS
        }
    )
    if unsupported_prompt_variants:
        raise ValueError(
            "Unsupported preview prompt_variant values: "
            f"{', '.join(unsupported_prompt_variants)}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = load_eval_cases(args.manifest)
    if args.limit_cases is not None:
        cases = cases[: args.limit_cases]

    if args.model_matrix:
        preview_model_configs = load_preview_model_configs(args.model_matrix)

        if not preview_model_configs:
            raise ValueError("No enabled preview model configs found in model matrix")

        _validate_preview_model_configs(preview_model_configs)

        if args.dry_run:
            plan = build_dry_run_plan(
                cases=cases,
                preview_model_configs=preview_model_configs,
            )
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
        runner = EvalRunner(
            semantic_parser=SemanticParserClient(),
            image_generator=preview_generators[0][1],
        )
        report = runner.run_cases_with_preview_generators(
            cases=cases,
            preview_generators=preview_generators,
            report_path=report_path,
        )
    else:
        if args.dry_run:
            plan = build_dry_run_plan(
                cases=cases,
                preview_model_configs=[
                    PreviewModelConfig(
                        run_id="default",
                        model="settings.REPLICATE_PREVIEW_MODEL",
                        model_version=None,
                        input_mapping="settings.REPLICATE_PREVIEW_INPUT_MAPPING",
                        prompt_variant="preview-garment-swap-v1",
                    )
                ],
            )
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0

        report_path = args.report_path or _default_report_path()
        runner = EvalRunner(
            semantic_parser=SemanticParserClient(),
            image_generator=ReplicatePreviewGenerator(),
        )
        report = runner.run_cases(cases=cases, report_path=report_path)

    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"Report written to {report_path}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
