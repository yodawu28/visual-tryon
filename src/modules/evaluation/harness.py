"""
Repeatable evaluation harness for virtual try-on model and prompt comparisons.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    anonymized_user_image_path: Path
    product_image_path: Path
    mask_path: Path | None
    manual_quality_notes: dict[str, str]


@dataclass(frozen=True)
class PreviewModelConfig:
    run_id: str
    model: str
    model_version: str | None
    input_mapping: str
    prompt_variant: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _resolve_manifest_path(manifest_path: Path, raw_path: str | None) -> Path | None:
    if raw_path is None:
        return None

    path = Path(raw_path)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def _resolve_required_manifest_path(manifest_path: Path, raw_path: str) -> Path:
    resolved_path = _resolve_manifest_path(manifest_path, raw_path)
    if resolved_path is None:
        raise ValueError("Required manifest path is missing")
    return resolved_path


def _safe_filename(value: str) -> str:
    safe_chars = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("-")
    return "".join(safe_chars).strip("-") or "case"


def load_eval_cases(manifest_path: Path) -> list[EvalCase]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = []

    for raw_case in payload.get("cases", []):
        mask_path = _resolve_manifest_path(manifest_path, raw_case.get("mask_path"))
        cases.append(
            EvalCase(
                case_id=raw_case["case_id"],
                anonymized_user_image_path=_resolve_required_manifest_path(
                    manifest_path,
                    raw_case["anonymized_user_image_path"],
                ),
                product_image_path=_resolve_required_manifest_path(
                    manifest_path,
                    raw_case["product_image_path"],
                ),
                mask_path=mask_path,
                manual_quality_notes=raw_case.get("manual_quality_notes", {}),
            )
        )

    return cases


def load_preview_model_configs(matrix_path: Path) -> list[PreviewModelConfig]:
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    preview_models = (
        payload.get("preview_models") if isinstance(payload, dict) else None
    )
    if not isinstance(preview_models, list):
        raise ValueError("preview_models must be a list")

    configs: list[PreviewModelConfig] = []
    seen_run_ids: set[str] = set()

    for index, raw_config in enumerate(preview_models):
        if not isinstance(raw_config, dict):
            raise ValueError(f"preview_models[{index}] must be an object")

        enabled = raw_config.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"preview_models[{index}].enabled must be a boolean")
        if enabled is False:
            continue

        run_id = _require_non_empty_string(raw_config, "run_id", index)
        if run_id in seen_run_ids:
            raise ValueError(f"Duplicate preview run_id: {run_id}")
        seen_run_ids.add(run_id)

        model_version = raw_config.get("model_version")
        if model_version is not None and (
            not isinstance(model_version, str) or not model_version.strip()
        ):
            raise ValueError(
                f"preview_models[{index}].model_version must be a string or null"
            )

        prompt_variant = raw_config.get(
            "prompt_variant",
            "preview-garment-swap-v1",
        )
        if not isinstance(prompt_variant, str) or not prompt_variant.strip():
            raise ValueError(
                f"preview_models[{index}].prompt_variant must be a non-empty string"
            )

        configs.append(
            PreviewModelConfig(
                run_id=run_id,
                model=_require_non_empty_string(raw_config, "model", index),
                model_version=model_version,
                input_mapping=_require_non_empty_string(
                    raw_config,
                    "input_mapping",
                    index,
                ),
                prompt_variant=prompt_variant,
            )
        )

    return configs


def _require_non_empty_string(
    raw_config: dict[str, Any],
    field_name: str,
    index: int,
) -> str:
    value = raw_config.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"preview_models[{index}].{field_name} must be a non-empty string"
        )
    return value


class EvalRunner:
    def __init__(self, *, semantic_parser: Any, image_generator: Any):
        self.semantic_parser = semantic_parser
        self.image_generator = image_generator

    def run_cases(self, *, cases: list[EvalCase], report_path: Path) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        output_dir = report_path.parent / f"{report_path.stem}-images"
        results = [
            self._run_case(eval_case, output_dir=output_dir) for eval_case in cases
        ]
        succeeded = sum(1 for result in results if result["status"] == "succeeded")
        failed = len(results) - succeeded
        report = {
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_cases": len(results),
                "succeeded": succeeded,
                "failed": failed,
            },
            "cases": results,
        }

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report

    def run_cases_with_preview_generators(
        self,
        *,
        cases: list[EvalCase],
        preview_generators: list[tuple[str, Any]],
        report_path: Path,
    ) -> dict[str, Any]:
        if not preview_generators:
            raise ValueError("At least one preview generator is required")

        started_at = datetime.now(timezone.utc).isoformat()
        output_dir = report_path.parent / f"{report_path.stem}-images"
        results = [
            self._run_case_with_preview_generators(
                eval_case,
                preview_generators=preview_generators,
                output_dir=output_dir,
            )
            for eval_case in cases
        ]
        preview_results = [
            preview_result
            for case_result in results
            for preview_result in case_result["preview_results"]
        ]
        succeeded = sum(
            1
            for preview_result in preview_results
            if preview_result["status"] == "succeeded"
        )
        failed_preview_runs = len(preview_results) - succeeded
        semantic_failed_cases = sum(
            1
            for result in results
            if result["status"] == "failed" and not result["preview_results"]
        )
        failed = failed_preview_runs + semantic_failed_cases
        report = {
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_cases": len(results),
                "preview_runs_per_case": len(preview_generators),
                "total_preview_runs": len(preview_results),
                "succeeded": succeeded,
                "failed": failed,
            },
            "cases": results,
        }

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report

    def _run_case_with_preview_generators(
        self,
        eval_case: EvalCase,
        *,
        preview_generators: list[tuple[str, Any]],
        output_dir: Path,
    ) -> dict[str, Any]:
        semantic_metadata = self.semantic_parser.get_runtime_metadata()
        input_hashes = {
            "user_image_sha256": file_sha256(eval_case.anonymized_user_image_path),
            "product_image_sha256": file_sha256(eval_case.product_image_path),
            "mask_sha256": (
                file_sha256(eval_case.mask_path) if eval_case.mask_path else None
            ),
        }
        case_started = time.perf_counter()
        user_image_b64 = _file_to_base64(eval_case.anonymized_user_image_path)
        product_image_b64 = _file_to_base64(eval_case.product_image_path)
        mask_b64 = _file_to_base64(eval_case.mask_path) if eval_case.mask_path else None

        try:
            analysis_started = time.perf_counter()
            analysis = self.semantic_parser.analyze_vto_context(
                user_image_b64=user_image_b64,
                product_image_b64=product_image_b64,
            )
            analysis_latency = time.perf_counter() - analysis_started
        except Exception as exc:
            return {
                "case_id": eval_case.case_id,
                "status": "failed",
                "error": str(exc),
                "input_hashes": input_hashes,
                "semantic": {
                    "provider": semantic_metadata["provider"],
                    "model": semantic_metadata["model"],
                    "prompt_version": semantic_metadata["semantic_prompt_version"],
                },
                "preview_results": [],
                "total_latency_seconds": time.perf_counter() - case_started,
                "manual_quality_notes": eval_case.manual_quality_notes,
            }

        preview_results = [
            self._run_preview_generator(
                run_id=run_id,
                image_generator=image_generator,
                eval_case=eval_case,
                user_image_b64=user_image_b64,
                product_image_b64=product_image_b64,
                mask_b64=mask_b64,
                inpainting_prompt=analysis.inpainting_prompt,
                output_dir=output_dir,
            )
            for run_id, image_generator in preview_generators
        ]

        preview_failed = any(
            preview_result["status"] == "failed" for preview_result in preview_results
        )

        return {
            "case_id": eval_case.case_id,
            "status": "failed" if preview_failed else "succeeded",
            "error": "One or more preview runs failed" if preview_failed else None,
            "input_hashes": input_hashes,
            "semantic": {
                "provider": semantic_metadata["provider"],
                "model": semantic_metadata["model"],
                "prompt_version": semantic_metadata["semantic_prompt_version"],
                "latency_seconds": analysis_latency,
                "confidence_score": analysis.confidence_score,
                "clothing_description": analysis.clothing_description,
                "body_pose": analysis.body_pose,
                "additional_notes": analysis.additional_notes,
            },
            "preview_results": preview_results,
            "total_latency_seconds": time.perf_counter() - case_started,
            "manual_quality_notes": eval_case.manual_quality_notes,
        }

    def _run_preview_generator(
        self,
        *,
        run_id: str,
        image_generator: Any,
        eval_case: EvalCase,
        user_image_b64: str,
        product_image_b64: str,
        mask_b64: str | None,
        inpainting_prompt: str,
        output_dir: Path,
    ) -> dict[str, Any]:
        preview_metadata: dict[str, Any | None] = {
            "model": None,
            "input_mapping": None,
            "prompt_version": None,
        }
        preview_started = time.perf_counter()

        try:
            raw_metadata = image_generator.get_runtime_metadata()
            preview_metadata = {
                "model": raw_metadata.get("preview_model"),
                "input_mapping": raw_metadata.get("preview_input_mapping"),
                "prompt_version": raw_metadata.get("preview_prompt_version"),
            }
            missing_fields = [
                field_name
                for field_name, value in {
                    "preview_model": preview_metadata["model"],
                    "preview_input_mapping": preview_metadata["input_mapping"],
                    "preview_prompt_version": preview_metadata["prompt_version"],
                }.items()
                if value is None
            ]
            if missing_fields:
                raise ValueError(
                    f"Missing preview metadata fields: {', '.join(missing_fields)}"
                )

            generated_image_b64 = image_generator.generate_tryon_from_b64(
                base_image_b64=user_image_b64,
                garment_image_b64=product_image_b64,
                inpainting_prompt=inpainting_prompt,
                mask_b64=mask_b64,
                size="1024x1024",
            )
            generated_image_bytes = base64.b64decode(generated_image_b64)
            output_dir.mkdir(parents=True, exist_ok=True)
            generated_image_path = (
                output_dir
                / f"{_safe_filename(eval_case.case_id)}-{_safe_filename(run_id)}.png"
            )
            generated_image_path.write_bytes(generated_image_bytes)

            return {
                "run_id": run_id,
                "status": "succeeded",
                "error": None,
                "model": preview_metadata["model"],
                "input_mapping": preview_metadata["input_mapping"],
                "prompt_version": preview_metadata["prompt_version"],
                "latency_seconds": time.perf_counter() - preview_started,
                "generated_image_bytes": len(generated_image_bytes),
                "generated_image_path": str(generated_image_path),
            }
        except Exception as exc:
            return {
                "run_id": run_id,
                "status": "failed",
                "error": str(exc),
                "model": preview_metadata["model"],
                "input_mapping": preview_metadata["input_mapping"],
                "prompt_version": preview_metadata["prompt_version"],
                "latency_seconds": time.perf_counter() - preview_started,
                "generated_image_bytes": None,
                "generated_image_path": None,
            }

    def _run_case(self, eval_case: EvalCase, *, output_dir: Path) -> dict[str, Any]:
        semantic_metadata = self.semantic_parser.get_runtime_metadata()
        preview_metadata = self.image_generator.get_runtime_metadata()
        input_hashes = {
            "user_image_sha256": file_sha256(eval_case.anonymized_user_image_path),
            "product_image_sha256": file_sha256(eval_case.product_image_path),
            "mask_sha256": (
                file_sha256(eval_case.mask_path) if eval_case.mask_path else None
            ),
        }
        case_started = time.perf_counter()

        try:
            user_image_b64 = _file_to_base64(eval_case.anonymized_user_image_path)
            product_image_b64 = _file_to_base64(eval_case.product_image_path)
            mask_b64 = (
                _file_to_base64(eval_case.mask_path) if eval_case.mask_path else None
            )

            analysis_started = time.perf_counter()
            analysis = self.semantic_parser.analyze_vto_context(
                user_image_b64=user_image_b64,
                product_image_b64=product_image_b64,
            )
            analysis_latency = time.perf_counter() - analysis_started

            preview_started = time.perf_counter()
            generated_image_b64 = self.image_generator.generate_tryon_from_b64(
                base_image_b64=user_image_b64,
                garment_image_b64=product_image_b64,
                inpainting_prompt=analysis.inpainting_prompt,
                mask_b64=mask_b64,
                size="1024x1024",
            )
            generated_image_bytes = base64.b64decode(generated_image_b64)
            output_dir.mkdir(parents=True, exist_ok=True)
            generated_image_path = (
                output_dir / f"{_safe_filename(eval_case.case_id)}.png"
            )
            generated_image_path.write_bytes(generated_image_bytes)
            preview_latency = time.perf_counter() - preview_started

            return {
                "case_id": eval_case.case_id,
                "status": "succeeded",
                "error": None,
                "input_hashes": input_hashes,
                "semantic": {
                    "provider": semantic_metadata["provider"],
                    "model": semantic_metadata["model"],
                    "prompt_version": semantic_metadata["semantic_prompt_version"],
                    "latency_seconds": analysis_latency,
                    "confidence_score": analysis.confidence_score,
                    "clothing_description": analysis.clothing_description,
                    "body_pose": analysis.body_pose,
                    "additional_notes": analysis.additional_notes,
                },
                "preview": {
                    "model": preview_metadata["preview_model"],
                    "input_mapping": preview_metadata["preview_input_mapping"],
                    "prompt_version": preview_metadata["preview_prompt_version"],
                    "latency_seconds": preview_latency,
                    "generated_image_bytes": len(generated_image_bytes),
                    "generated_image_path": str(generated_image_path),
                },
                "total_latency_seconds": time.perf_counter() - case_started,
                "manual_quality_notes": eval_case.manual_quality_notes,
            }
        except Exception as exc:
            return {
                "case_id": eval_case.case_id,
                "status": "failed",
                "error": str(exc),
                "input_hashes": input_hashes,
                "semantic": {
                    "provider": semantic_metadata["provider"],
                    "model": semantic_metadata["model"],
                    "prompt_version": semantic_metadata["semantic_prompt_version"],
                },
                "preview": {
                    "model": preview_metadata["preview_model"],
                    "input_mapping": preview_metadata["preview_input_mapping"],
                    "prompt_version": preview_metadata["preview_prompt_version"],
                },
                "total_latency_seconds": time.perf_counter() - case_started,
                "manual_quality_notes": eval_case.manual_quality_notes,
            }
