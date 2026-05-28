"""
Evaluation harness for avatar-based garment preview.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.modules.avatar_preview import (
    PREVIEW_CONTEXT_PROMPT_VERSION,
    AvatarProfileInput,
    DerivedAvatarProfile,
    build_avatar_preview_context_prompt,
    build_preview_cache_key,
    derive_avatar_profile,
    report_safe_profile,
)
from src.modules.evaluation.harness import (
    PreviewModelConfig,
    _file_to_base64,
    _resolve_required_manifest_path,
    _safe_filename,
    file_sha256,
)


@dataclass(frozen=True)
class AvatarEvalCase:
    case_id: str
    avatar_image_path: Path
    product_image_path: Path
    profile: AvatarProfileInput
    derived_profile: DerivedAvatarProfile
    report_profile: dict[str, object]
    manual_quality_notes: dict[str, str]


def load_avatar_eval_cases(manifest_path: Path) -> list[AvatarEvalCase]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases: list[AvatarEvalCase] = []

    for raw_case in payload.get("cases", []):
        profile = AvatarProfileInput.model_validate(raw_case["body_profile"])
        cases.append(
            AvatarEvalCase(
                case_id=raw_case["case_id"],
                avatar_image_path=_resolve_required_manifest_path(
                    manifest_path,
                    raw_case["avatar_image_path"],
                ),
                product_image_path=_resolve_required_manifest_path(
                    manifest_path,
                    raw_case["product_image_path"],
                ),
                profile=profile,
                derived_profile=derive_avatar_profile(profile),
                report_profile=report_safe_profile(profile),
                manual_quality_notes=raw_case.get("manual_quality_notes", {}),
            )
        )

    return cases


def build_avatar_dry_run_plan(
    cases: list[AvatarEvalCase],
    preview_model_configs: list[PreviewModelConfig],
) -> dict[str, Any]:
    planned_runs = [
        {
            "case_id": eval_case.case_id,
            "input_mode": eval_case.report_profile["input_mode"],
            "derived_profile": eval_case.report_profile["derived_profile"],
            "run_id": preview_config.run_id,
            "model": preview_config.model,
            "input_mapping": preview_config.input_mapping,
            "prompt_variant": preview_config.prompt_variant,
            "avatar_prompt_variant": PREVIEW_CONTEXT_PROMPT_VERSION,
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


class AvatarEvalRunner:
    def run_cases_with_preview_generators(
        self,
        *,
        cases: list[AvatarEvalCase],
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
        failed = len(preview_results) - succeeded
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
        eval_case: AvatarEvalCase,
        *,
        preview_generators: list[tuple[str, Any]],
        output_dir: Path,
    ) -> dict[str, Any]:
        case_started = time.perf_counter()
        avatar_image_sha256 = file_sha256(eval_case.avatar_image_path)
        product_image_sha256 = file_sha256(eval_case.product_image_path)
        input_hashes = {
            "avatar_image_sha256": avatar_image_sha256,
            "product_image_sha256": product_image_sha256,
        }
        avatar_image_b64 = _file_to_base64(eval_case.avatar_image_path)
        product_image_b64 = _file_to_base64(eval_case.product_image_path)
        prompt = build_avatar_preview_context_prompt(eval_case.derived_profile)

        preview_results = [
            self._run_preview_generator(
                run_id=run_id,
                image_generator=image_generator,
                eval_case=eval_case,
                avatar_image_b64=avatar_image_b64,
                product_image_b64=product_image_b64,
                prompt=prompt,
                avatar_image_sha256=avatar_image_sha256,
                product_image_sha256=product_image_sha256,
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
            "avatar_profile": eval_case.report_profile,
            "avatar_prompt_version": PREVIEW_CONTEXT_PROMPT_VERSION,
            "preview_results": preview_results,
            "total_latency_seconds": time.perf_counter() - case_started,
            "manual_quality_notes": eval_case.manual_quality_notes,
        }

    def _run_preview_generator(
        self,
        *,
        run_id: str,
        image_generator: Any,
        eval_case: AvatarEvalCase,
        avatar_image_b64: str,
        product_image_b64: str,
        prompt: str,
        avatar_image_sha256: str,
        product_image_sha256: str,
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
            preview_model = _require_preview_metadata_string(
                raw_metadata,
                "preview_model",
            )
            preview_input_mapping = _require_preview_metadata_string(
                raw_metadata,
                "preview_input_mapping",
            )
            preview_prompt_version = _require_preview_metadata_string(
                raw_metadata,
                "preview_prompt_version",
            )
            preview_metadata = {
                "model": preview_model,
                "input_mapping": preview_input_mapping,
                "prompt_version": preview_prompt_version,
            }

            generated_image_b64 = image_generator.generate_tryon_from_b64(
                base_image_b64=avatar_image_b64,
                garment_image_b64=product_image_b64,
                inpainting_prompt=prompt,
                mask_b64=None,
                size="1024x1024",
            )
            generated_image_bytes = base64.b64decode(
                generated_image_b64,
                validate=True,
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            generated_image_path = (
                output_dir
                / f"{_safe_filename(eval_case.case_id)}-{_safe_filename(run_id)}.png"
            )
            generated_image_path.write_bytes(generated_image_bytes)
            seed = getattr(image_generator, "seed", None)

            return {
                "run_id": run_id,
                "status": "succeeded",
                "error": None,
                "model": preview_model,
                "input_mapping": preview_input_mapping,
                "prompt_version": preview_prompt_version,
                "latency_seconds": time.perf_counter() - preview_started,
                "generated_image_bytes": len(generated_image_bytes),
                "generated_image_path": str(generated_image_path),
                "preview_cache_key": build_preview_cache_key(
                    avatar_image_sha256=avatar_image_sha256,
                    product_image_sha256=product_image_sha256,
                    preview_model_id=preview_model,
                    preview_prompt_version=preview_prompt_version,
                    input_mapping=preview_input_mapping,
                    seed=seed if isinstance(seed, int) else None,
                ),
            }
        except Exception as exc:
            return {
                "run_id": run_id,
                "status": "failed",
                "error": _redact_error(str(exc)),
                "model": preview_metadata["model"],
                "input_mapping": preview_metadata["input_mapping"],
                "prompt_version": preview_metadata["prompt_version"],
                "latency_seconds": time.perf_counter() - preview_started,
                "generated_image_bytes": None,
                "generated_image_path": None,
                "preview_cache_key": None,
            }


def _require_preview_metadata_string(
    raw_metadata: dict[str, Any],
    field_name: str,
) -> str:
    value = raw_metadata.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing preview metadata fields: {field_name}")
    return value


def _redact_error(error_message: str) -> str:
    sanitized = re.sub(
        r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/=]{40,}(?![A-Za-z0-9+/=])",
        "[redacted-token]",
        error_message,
    )
    sanitized = re.sub(
        r"(?:/[A-Za-z0-9._-]+){2,}",
        "[redacted-path]",
        sanitized,
    )
    return sanitized[:300]
