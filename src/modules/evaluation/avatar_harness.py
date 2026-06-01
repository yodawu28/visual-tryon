"""
Evaluation harness for avatar-based garment preview.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.modules.avatar_preview import (
    AVATAR_PROMPT_VERSION,
    PREVIEW_CONTEXT_PROMPT_VERSION,
    AvatarProfileInput,
    AvatarFraming,
    DerivedAvatarProfile,
    FashnVtonCategory,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
    avatar_framing_for_garment_region,
    build_avatar_cache_key,
    build_avatar_generation_prompt,
    build_avatar_preview_context_prompt,
    default_sleeve_length_for_garment_type,
    derive_avatar_profile,
    fashn_vton_category_for_garment,
    report_safe_profile,
    resolve_garment_region,
)
from src.modules.avatar_preview.cache_keys import (
    build_preview_cache_key,
    preview_context_prompt_hash,
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
    avatar_image_path: Path | None
    avatar_image_source: str
    garment_type: GarmentType | None
    garment_sleeve_length: GarmentSleeveLength
    garment_region: GarmentRegion
    fashn_category: FashnVtonCategory
    avatar_framing: AvatarFraming
    product_image_path: Path
    profile: AvatarProfileInput
    derived_profile: DerivedAvatarProfile
    report_profile: dict[str, object]
    manual_quality_notes: dict[str, str]


@dataclass(frozen=True)
class ResolvedAvatarImage:
    path: Path
    source: str
    cache_hit: bool | None
    cache_key: str | None
    prompt_version: str | None
    prompt_sha256: str | None
    model: str | None
    avatar_catalog_version: str | None
    framing: AvatarFraming

    def report_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": str(self.path),
            "cache_hit": self.cache_hit,
            "cache_key": self.cache_key,
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_sha256,
            "model": self.model,
            "avatar_catalog_version": self.avatar_catalog_version,
            "framing": self.framing.value,
        }


def load_avatar_eval_cases(manifest_path: Path) -> list[AvatarEvalCase]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases: list[AvatarEvalCase] = []

    for raw_case in payload.get("cases", []):
        profile = AvatarProfileInput.model_validate(raw_case["body_profile"])
        raw_avatar_image_path = raw_case.get("avatar_image_path")
        avatar_image_path = (
            _resolve_required_manifest_path(manifest_path, raw_avatar_image_path)
            if raw_avatar_image_path
            else None
        )
        avatar_image_source = raw_case.get(
            "avatar_image_source",
            (
                "provided_image"
                if avatar_image_path is not None
                else "generated_synthetic_person_photo"
            ),
        )
        if avatar_image_source not in {
            "provided_image",
            "generated_synthetic_person_photo",
        }:
            raise ValueError(f"Unsupported avatar_image_source: {avatar_image_source}")
        garment_type = (
            GarmentType(raw_case["garment_type"])
            if raw_case.get("garment_type") is not None
            else None
        )
        garment_region = resolve_garment_region(
            garment_type=garment_type,
            garment_region=(
                GarmentRegion(raw_case["garment_region"])
                if raw_case.get("garment_region") is not None
                else None
            ),
        )
        garment_sleeve_length = (
            GarmentSleeveLength(raw_case["garment_sleeve_length"])
            if raw_case.get("garment_sleeve_length") is not None
            else default_sleeve_length_for_garment_type(garment_type)
        )
        fashn_category = (
            FashnVtonCategory(raw_case["fashn_category"])
            if raw_case.get("fashn_category") is not None
            else fashn_vton_category_for_garment(
                garment_type=garment_type,
                garment_region=garment_region,
            )
        )
        avatar_framing = avatar_framing_for_garment_region(garment_region)
        cases.append(
            AvatarEvalCase(
                case_id=raw_case["case_id"],
                avatar_image_path=avatar_image_path,
                avatar_image_source=avatar_image_source,
                garment_type=garment_type,
                garment_sleeve_length=garment_sleeve_length,
                garment_region=garment_region,
                fashn_category=fashn_category,
                avatar_framing=avatar_framing,
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
            "avatar_image_source": eval_case.avatar_image_source,
            "garment_type": (
                eval_case.garment_type.value
                if eval_case.garment_type is not None
                else None
            ),
            "garment_region": eval_case.garment_region.value,
            "garment_sleeve_length": eval_case.garment_sleeve_length.value,
            "fashn_category": eval_case.fashn_category.value,
            "avatar_framing": eval_case.avatar_framing.value,
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
    def generate_avatar_images_for_cases(
        self,
        *,
        cases: list[AvatarEvalCase],
        avatar_generator: Any,
        avatar_cache_dir: Path,
        report_path: Path,
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        results = [
            self._generate_avatar_image_for_case(
                eval_case,
                avatar_generator=avatar_generator,
                avatar_cache_dir=avatar_cache_dir,
            )
            for eval_case in cases
        ]
        report = {
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_cases": len(results),
                "generated": sum(
                    1
                    for result in results
                    if result["status"] == "succeeded"
                    and result["avatar_image"]["cache_hit"] is False
                ),
                "cache_hits": sum(
                    1
                    for result in results
                    if result["status"] == "succeeded"
                    and result["avatar_image"]["cache_hit"] is True
                ),
                "failed": sum(1 for result in results if result["status"] == "failed"),
            },
            "cases": results,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report

    def _generate_avatar_image_for_case(
        self,
        eval_case: AvatarEvalCase,
        *,
        avatar_generator: Any,
        avatar_cache_dir: Path,
    ) -> dict[str, Any]:
        case_started = time.perf_counter()
        try:
            resolved_avatar = _resolve_avatar_image(
                eval_case,
                avatar_generator=avatar_generator,
                avatar_cache_dir=avatar_cache_dir,
            )
            return {
                "case_id": eval_case.case_id,
                "status": "succeeded",
                "error": None,
                "avatar_profile": eval_case.report_profile,
                "avatar_image": resolved_avatar.report_payload(),
                "garment_type": (
                    eval_case.garment_type.value
                    if eval_case.garment_type is not None
                    else None
                ),
                "garment_region": eval_case.garment_region.value,
                "garment_sleeve_length": eval_case.garment_sleeve_length.value,
                "fashn_category": eval_case.fashn_category.value,
                "avatar_framing": eval_case.avatar_framing.value,
                "avatar_image_sha256": file_sha256(resolved_avatar.path),
                "latency_seconds": time.perf_counter() - case_started,
                "manual_quality_notes": eval_case.manual_quality_notes,
            }
        except Exception as exc:
            return {
                "case_id": eval_case.case_id,
                "status": "failed",
                "error": _redact_error(str(exc)),
                "avatar_profile": eval_case.report_profile,
                "avatar_image": None,
                "avatar_image_sha256": None,
                "latency_seconds": time.perf_counter() - case_started,
                "manual_quality_notes": eval_case.manual_quality_notes,
            }

    def run_cases_with_preview_generators(
        self,
        *,
        cases: list[AvatarEvalCase],
        preview_generators: list[tuple[str, Any]],
        report_path: Path,
        avatar_generator: Any | None = None,
        avatar_cache_dir: Path | None = None,
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
                avatar_generator=avatar_generator,
                avatar_cache_dir=avatar_cache_dir,
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
        avatar_generator: Any | None,
        avatar_cache_dir: Path | None,
    ) -> dict[str, Any]:
        case_started = time.perf_counter()
        resolved_avatar = _resolve_avatar_image(
            eval_case,
            avatar_generator=avatar_generator,
            avatar_cache_dir=avatar_cache_dir,
        )
        avatar_image_sha256 = file_sha256(resolved_avatar.path)
        product_image_sha256 = file_sha256(eval_case.product_image_path)
        input_hashes = {
            "avatar_image_sha256": avatar_image_sha256,
            "product_image_sha256": product_image_sha256,
        }
        avatar_image_b64 = _file_to_base64(resolved_avatar.path)
        product_image_b64 = _file_to_base64(eval_case.product_image_path)
        prompt = build_avatar_preview_context_prompt(
            eval_case.derived_profile,
            avatar_framing=eval_case.avatar_framing,
            garment_region=eval_case.garment_region,
            garment_type=eval_case.garment_type,
        )
        prompt_sha256 = preview_context_prompt_hash(prompt)

        preview_results = [
            self._run_preview_generator(
                run_id=run_id,
                image_generator=image_generator,
                eval_case=eval_case,
                avatar_image_b64=avatar_image_b64,
                product_image_b64=product_image_b64,
                prompt=prompt,
                prompt_sha256=prompt_sha256,
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
            "garment_type": (
                eval_case.garment_type.value
                if eval_case.garment_type is not None
                else None
            ),
            "garment_region": eval_case.garment_region.value,
            "garment_sleeve_length": eval_case.garment_sleeve_length.value,
            "fashn_category": eval_case.fashn_category.value,
            "avatar_framing": eval_case.avatar_framing.value,
            "avatar_image": resolved_avatar.report_payload(),
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
        prompt_sha256: str,
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
            set_case_context = getattr(type(image_generator), "set_case_context", None)
            if callable(set_case_context):
                image_generator.set_case_context(
                    case_id=eval_case.case_id,
                    garment_type=(
                        eval_case.garment_type.value
                        if eval_case.garment_type is not None
                        else None
                    ),
                    garment_region=eval_case.garment_region.value,
                    garment_sleeve_length=eval_case.garment_sleeve_length.value,
                    fashn_category=eval_case.fashn_category.value,
                )

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
                "fashn_category": eval_case.fashn_category.value,
                "preview_context_prompt_sha256": prompt_sha256,
                "latency_seconds": time.perf_counter() - preview_started,
                "generated_image_bytes": len(generated_image_bytes),
                "generated_image_path": str(generated_image_path),
                "preview_cache_key": build_preview_cache_key(
                    avatar_image_sha256=avatar_image_sha256,
                    product_image_sha256=product_image_sha256,
                    preview_context_prompt_sha256=prompt_sha256,
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
                "fashn_category": eval_case.fashn_category.value,
                "preview_context_prompt_sha256": prompt_sha256,
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


def _resolve_avatar_image(
    eval_case: AvatarEvalCase,
    *,
    avatar_generator: Any | None,
    avatar_cache_dir: Path | None,
) -> ResolvedAvatarImage:
    if eval_case.avatar_image_path is not None:
        return ResolvedAvatarImage(
            path=eval_case.avatar_image_path,
            source=eval_case.avatar_image_source,
            cache_hit=None,
            cache_key=None,
            prompt_version=None,
            prompt_sha256=None,
            model=None,
            avatar_catalog_version=None,
            framing=eval_case.avatar_framing,
        )

    if avatar_generator is None:
        raise ValueError(
            "avatar_generator is required when avatar_image_path is omitted"
        )
    if avatar_cache_dir is None:
        raise ValueError(
            "avatar_cache_dir is required when avatar_image_path is omitted"
        )

    raw_metadata = avatar_generator.get_runtime_metadata()
    avatar_model = _require_avatar_metadata_string(raw_metadata, "avatar_model")
    avatar_catalog_version = _require_avatar_metadata_string(
        raw_metadata,
        "avatar_catalog_version",
    )
    prompt = build_avatar_generation_prompt(
        eval_case.derived_profile,
        avatar_framing=eval_case.avatar_framing,
        garment_region=eval_case.garment_region,
        garment_sleeve_length=eval_case.garment_sleeve_length,
    )
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_key = build_avatar_cache_key(
        derived_profile=eval_case.derived_profile,
        avatar_model_id=avatar_model,
        avatar_catalog_version=avatar_catalog_version,
        avatar_framing=eval_case.avatar_framing,
        garment_region=eval_case.garment_region,
        garment_type=eval_case.garment_type,
        garment_sleeve_length=eval_case.garment_sleeve_length,
    )
    avatar_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = avatar_cache_dir / f"{cache_key.replace(':', '-')}.png"

    if cache_path.exists():
        cache_hit = True
    else:
        generated_avatar_b64 = avatar_generator.generate_avatar(
            prompt=prompt,
            size="1024x1024",
        )
        generated_avatar_bytes = base64.b64decode(
            generated_avatar_b64,
            validate=True,
        )
        cache_path.write_bytes(generated_avatar_bytes)
        cache_hit = False

    return ResolvedAvatarImage(
        path=cache_path,
        source=eval_case.avatar_image_source,
        cache_hit=cache_hit,
        cache_key=cache_key,
        prompt_version=AVATAR_PROMPT_VERSION,
        prompt_sha256=prompt_sha256,
        model=avatar_model,
        avatar_catalog_version=avatar_catalog_version,
        framing=eval_case.avatar_framing,
    )


def _require_avatar_metadata_string(
    raw_metadata: dict[str, Any],
    field_name: str,
) -> str:
    value = raw_metadata.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing avatar metadata fields: {field_name}")
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
