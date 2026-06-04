"""
Run multimodal analyzer evaluation for avatar try-on planning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.modules.avatar_preview.profile import (
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)
from src.modules.avatar_preview.tryon_analyzer import (
    OllamaTryOnAnalyzer,
    TryOnIntent,
)


@dataclass(frozen=True)
class AnalyzerEvalCase:
    case_id: str
    avatar_image_path: Path
    product_image_path: Path
    expected: dict[str, str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run avatar try-on multimodal analyzer eval cases"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument(
        "--model",
        dest="models",
        action="append",
        default=[],
        help="Ollama model to evaluate. Repeat for multiple models.",
    )
    parser.add_argument(
        "--ollama-base-url",
        default="http://127.0.0.1:11434",
        help="Ollama base URL",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--limit-cases", type=_positive_int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def load_analyzer_eval_cases(manifest_path: Path) -> list[AnalyzerEvalCase]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = []
    for index, raw_case in enumerate(payload.get("cases", [])):
        case_id = _require_string(raw_case, "case_id", index)
        cases.append(
            AnalyzerEvalCase(
                case_id=case_id,
                avatar_image_path=_resolve_required_path(
                    manifest_path,
                    _require_string(raw_case, "avatar_image_path", index),
                ),
                product_image_path=_resolve_required_path(
                    manifest_path,
                    _require_string(raw_case, "product_image_path", index),
                ),
                expected=_normalize_expected(raw_case.get("expected", {})),
            )
        )
    return cases


def build_dry_run_plan(
    *,
    cases: list[AnalyzerEvalCase],
    models: list[str],
) -> dict[str, Any]:
    planned_runs = [
        {
            "case_id": eval_case.case_id,
            "model": model,
            "expected": eval_case.expected,
        }
        for eval_case in cases
        for model in models
    ]
    return {
        "summary": {
            "total_cases": len(cases),
            "analyzer_runs_per_case": len(models),
            "total_analyzer_runs": len(planned_runs),
        },
        "planned_runs": planned_runs,
    }


def build_analyzer_from_args(
    args: argparse.Namespace,
    *,
    model: str,
) -> OllamaTryOnAnalyzer:
    return OllamaTryOnAnalyzer(
        model=model,
        base_url=args.ollama_base_url,
        timeout=args.timeout,
    )


def run_cases(
    *,
    cases: list[AnalyzerEvalCase],
    models: list[str],
    args: argparse.Namespace,
    report_path: Path,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    results = [
        _run_case(eval_case=eval_case, models=models, args=args) for eval_case in cases
    ]
    analyzer_results = [
        analyzer_result
        for case_result in results
        for analyzer_result in case_result["analyzer_results"]
    ]
    succeeded = sum(
        1
        for analyzer_result in analyzer_results
        if analyzer_result["status"] == "succeeded"
    )
    report = {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_cases": len(results),
            "analyzer_runs_per_case": len(models),
            "total_analyzer_runs": len(analyzer_results),
            "succeeded": succeeded,
            "failed": len(analyzer_results) - succeeded,
        },
        "cases": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    models = args.models or ["qwen2.5vl:7b"]
    cases = load_analyzer_eval_cases(args.manifest)
    if args.limit_cases is not None:
        cases = cases[: args.limit_cases]

    if args.dry_run:
        print(
            json.dumps(
                build_dry_run_plan(cases=cases, models=models),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    report_path = args.report_path or _default_report_path()
    report = run_cases(cases=cases, models=models, args=args, report_path=report_path)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"Report written to {report_path}")
    return 0


def _run_case(
    *,
    eval_case: AnalyzerEvalCase,
    models: list[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    avatar_bytes = eval_case.avatar_image_path.read_bytes()
    garment_bytes = eval_case.product_image_path.read_bytes()
    return {
        "case_id": eval_case.case_id,
        "input_hashes": {
            "avatar_image_sha256": _sha256_bytes(avatar_bytes),
            "product_image_sha256": _sha256_bytes(garment_bytes),
        },
        "expected": eval_case.expected,
        "analyzer_results": [
            _run_analyzer(
                model=model,
                args=args,
                avatar_bytes=avatar_bytes,
                garment_bytes=garment_bytes,
                expected=eval_case.expected,
            )
            for model in models
        ],
    }


def _run_analyzer(
    *,
    model: str,
    args: argparse.Namespace,
    avatar_bytes: bytes,
    garment_bytes: bytes,
    expected: dict[str, str],
) -> dict[str, Any]:
    analyzer = build_analyzer_from_args(args, model=model)
    metadata = analyzer.get_runtime_metadata()
    started = time.perf_counter()
    try:
        intent = analyzer.analyze_images(
            avatar_image=avatar_bytes,
            garment_image=garment_bytes,
        )
        return {
            "status": "succeeded",
            "error": None,
            "latency_seconds": time.perf_counter() - started,
            "metadata": metadata,
            "intent": intent.model_dump(mode="json"),
            "field_scores": _score_expected_fields(intent, expected),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "latency_seconds": time.perf_counter() - started,
            "metadata": metadata,
            "intent": None,
            "field_scores": {},
        }


def _score_expected_fields(
    intent: TryOnIntent,
    expected: dict[str, str],
) -> dict[str, bool]:
    expected_to_actual = {
        "garment_region": intent.garment_region.value,
        "garment_type": intent.garment_type.value,
        "sleeve_length": intent.sleeve_length.value,
    }
    return {
        field_name: expected_to_actual[field_name] == expected_value
        for field_name, expected_value in expected.items()
        if field_name in expected_to_actual
    }


def _normalize_expected(raw_expected: dict[str, Any]) -> dict[str, str]:
    if not isinstance(raw_expected, dict):
        raise ValueError("expected must be an object")
    normalized: dict[str, str] = {}
    if "garment_region" in raw_expected:
        normalized["garment_region"] = GarmentRegion(
            str(raw_expected["garment_region"])
        ).value
    if "garment_type" in raw_expected:
        normalized["garment_type"] = GarmentType(
            str(raw_expected["garment_type"])
        ).value
    if "sleeve_length" in raw_expected:
        normalized["sleeve_length"] = GarmentSleeveLength(
            str(raw_expected["sleeve_length"])
        ).value
    return normalized


def _default_report_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("data/eval/reports") / f"avatar-analyzer-eval-{timestamp}.json"


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _resolve_required_path(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def _require_string(raw_case: dict[str, Any], field_name: str, index: int) -> str:
    value = raw_case.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"cases[{index}].{field_name} must be a non-empty string")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
