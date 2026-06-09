"""
Visual try-on engine for kiosk personalized previews.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.modules.avatar_preview.tryon_analyzer import (
    TryOnIntent,
    build_multimodal_tryon_prompt,
)

KIOSK_VISUAL_TRYON_PROMPT_VERSION = "kiosk-visual-tryon-v1"


@dataclass(frozen=True)
class KioskVisualTryOnResult:
    generated_image: str
    personalized_tryon_key: str
    personalized_tryon_path: Path
    metadata_path: Path
    cache_hit: bool
    model: str
    prompt_version: str
    input_mapping: str | None
    generation_time_seconds: float
    multimodal_analysis_applied: bool
    tryon_intent: dict[str, Any] | None
    analyzer_model: str | None
    analyzer_prompt_version: str | None
    warnings: list[str]


class KioskVisualTryOnService:
    """
    Generate and cache personalized visual try-on images for kiosk sessions.

    This service intentionally handles visual generation only. Fit and size
    recommendation stay in the separate fit intelligence layer.
    """

    TRYON_PREFIX = "kiosk-tryon:v1:"

    def __init__(
        self,
        *,
        tryon_dir: Path,
        generator: Any,
        tryon_analyzer: Any | None = None,
    ) -> None:
        self.tryon_dir = Path(tryon_dir)
        self.images_dir = self.tryon_dir / "images"
        self.metadata_dir = self.tryon_dir / "metadata"
        self.generator = generator
        self.tryon_analyzer = tryon_analyzer
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def generate_tryon(
        self,
        *,
        session_id: str,
        garment_id: str,
        user_image: bytes,
        garment_image: bytes,
        garment_category: str,
        garment_type: str | None = None,
        use_multimodal_analysis: bool = True,
        size: str = "1024x1024",
    ) -> KioskVisualTryOnResult:
        if not user_image:
            raise ValueError("user_image must not be empty")
        if not garment_image:
            raise ValueError("garment_image must not be empty")

        start_time = time.time()
        base_prompt = build_kiosk_visual_tryon_prompt(
            garment_category=garment_category,
            garment_type=garment_type,
        )
        warnings: list[str] = []
        tryon_intent: TryOnIntent | None = None
        analyzer_metadata: dict[str, Any] = {}

        if use_multimodal_analysis:
            if self.tryon_analyzer is None:
                warnings.append(
                    "multimodal analysis skipped because analyzer is not configured"
                )
            else:
                try:
                    analyzer_metadata = self.tryon_analyzer.get_runtime_metadata()
                    analyzed_intent = self.tryon_analyzer.analyze_images(
                        avatar_image=user_image,
                        garment_image=garment_image,
                    )
                    tryon_intent = (
                        analyzed_intent
                        if isinstance(analyzed_intent, TryOnIntent)
                        else TryOnIntent.model_validate(analyzed_intent)
                    )
                except Exception as exc:
                    warnings.append(
                        "multimodal analysis failed; deterministic prompt used: "
                        f"{exc}"
                    )

        prompt = base_prompt
        if tryon_intent is not None:
            prompt = build_multimodal_tryon_prompt(
                base_prompt=base_prompt,
                intent=tryon_intent,
            )

        generator_metadata = self.generator.get_runtime_metadata()
        model = _require_metadata_string(generator_metadata, "preview_model")
        prompt_version = _require_metadata_string(
            generator_metadata,
            "preview_prompt_version",
        )
        input_mapping = _optional_metadata_string(
            generator_metadata,
            "preview_input_mapping",
        )
        user_image_sha256 = hashlib.sha256(user_image).hexdigest()
        garment_image_sha256 = hashlib.sha256(garment_image).hexdigest()
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        personalized_tryon_key = self._build_cache_key(
            session_id=session_id,
            garment_id=garment_id,
            user_image_sha256=user_image_sha256,
            garment_image_sha256=garment_image_sha256,
            prompt_sha256=prompt_sha256,
            model=model,
            prompt_version=prompt_version,
            input_mapping=input_mapping,
            seed=_generator_seed(self.generator),
        )
        image_path = self._image_path(personalized_tryon_key)
        metadata_path = self._metadata_path(personalized_tryon_key)
        cache_hit = image_path.exists() and metadata_path.exists()

        if cache_hit:
            generated_bytes = image_path.read_bytes()
        else:
            generated_image = self.generator.generate_tryon_from_b64(
                base_image_b64=base64.b64encode(user_image).decode("utf-8"),
                garment_image_b64=base64.b64encode(garment_image).decode("utf-8"),
                inpainting_prompt=prompt,
                mask_b64=None,
                size=size,
            )
            generated_bytes = _decode_base64_payload(
                generated_image,
                field_name="generated_image",
            )
            _write_bytes(image_path, generated_bytes)
            _write_text(
                metadata_path,
                json.dumps(
                    {
                        "personalized_tryon_key": personalized_tryon_key,
                        "session_id": session_id,
                        "garment_id": garment_id,
                        "user_image_sha256": user_image_sha256,
                        "garment_image_sha256": garment_image_sha256,
                        "generated_image_sha256": hashlib.sha256(
                            generated_bytes
                        ).hexdigest(),
                        "prompt_sha256": prompt_sha256,
                        "kiosk_prompt_version": KIOSK_VISUAL_TRYON_PROMPT_VERSION,
                        "preview_model": model,
                        "preview_prompt_version": prompt_version,
                        "preview_input_mapping": input_mapping,
                        "garment_category": garment_category,
                        "garment_type": garment_type,
                        "multimodal_analysis_applied": tryon_intent is not None,
                        "tryon_intent": (
                            tryon_intent.model_dump(mode="json")
                            if tryon_intent
                            else None
                        ),
                        "analyzer_model": analyzer_metadata.get("model"),
                        "analyzer_prompt_version": analyzer_metadata.get(
                            "analyzer_prompt_version"
                        ),
                        "warnings": warnings,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                    indent=2,
                    sort_keys=True,
                ),
            )

        return KioskVisualTryOnResult(
            generated_image=base64.b64encode(generated_bytes).decode("utf-8"),
            personalized_tryon_key=personalized_tryon_key,
            personalized_tryon_path=image_path,
            metadata_path=metadata_path,
            cache_hit=cache_hit,
            model=model,
            prompt_version=prompt_version,
            input_mapping=input_mapping,
            generation_time_seconds=time.time() - start_time,
            multimodal_analysis_applied=tryon_intent is not None,
            tryon_intent=(
                tryon_intent.model_dump(mode="json") if tryon_intent else None
            ),
            analyzer_model=analyzer_metadata.get("model"),
            analyzer_prompt_version=analyzer_metadata.get("analyzer_prompt_version"),
            warnings=warnings,
        )

    def _build_cache_key(
        self,
        *,
        session_id: str,
        garment_id: str,
        user_image_sha256: str,
        garment_image_sha256: str,
        prompt_sha256: str,
        model: str,
        prompt_version: str,
        input_mapping: str | None,
        seed: int | None,
    ) -> str:
        payload = {
            "session_id": session_id,
            "garment_id": garment_id,
            "user_image_sha256": user_image_sha256,
            "garment_image_sha256": garment_image_sha256,
            "prompt_sha256": prompt_sha256,
            "model": model,
            "prompt_version": prompt_version,
            "input_mapping": input_mapping,
            "seed": seed,
            "scope": "kiosk_personalized_visual_tryon",
            "version": KIOSK_VISUAL_TRYON_PROMPT_VERSION,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"{self.TRYON_PREFIX}{digest}"

    def _image_path(self, cache_key: str) -> Path:
        return self.images_dir / f"{_safe_cache_key_filename(cache_key)}.png"

    def _metadata_path(self, cache_key: str) -> Path:
        return self.metadata_dir / f"{_safe_cache_key_filename(cache_key)}.json"


def build_kiosk_visual_tryon_prompt(
    *,
    garment_category: str,
    garment_type: str | None = None,
) -> str:
    normalized_category = garment_category.strip().lower()
    garment_label = garment_type.strip() if garment_type else normalized_category
    scope_instruction = _scope_instruction(normalized_category)
    return (
        "Use IMAGE 1 as the real kiosk user capture and IMAGE 2 only as the "
        "garment reference. Create a realistic personalized visual try-on "
        "preview for the user. "
        f"The selected garment category is {normalized_category}; garment type is "
        f"{garment_label}. {scope_instruction} "
        "Keep the user's face, body proportions, pose, hands, skin, visible "
        "non-target clothing, background, camera framing, and lighting stable. "
        "Preserve the garment color, fabric texture, neckline, sleeve length, "
        "hem, logos, text, numbers, patterns, panels, trims, and visible design "
        "details as much as the model allows. Do not invent extra logos, brand "
        "marks, accessories, jackets, or layered sleeves. Do not use the garment "
        "image background as part of the output. This output is a visual preview "
        "only and must not imply size accuracy or fit recommendation."
    )


def _scope_instruction(category: str) -> str:
    if category == "bottoms":
        return (
            "Replace only the lower-body garment on the user; keep the user's "
            "top, face, arms, shoes, and background unchanged."
        )
    if category == "one_pieces":
        return (
            "Apply the full-body or one-piece garment to the user while keeping "
            "the user's pose, face, hands, legs, and background stable."
        )
    return (
        "Replace only the upper-body garment on the user; keep the user's pants, "
        "shorts, shoes, face, hands, legs, and background unchanged."
    )


def _decode_base64_payload(payload: str, *, field_name: str) -> bytes:
    if not payload:
        raise ValueError(f"{field_name} payload is empty")
    normalized = payload.strip()
    if normalized.startswith("data:"):
        try:
            normalized = normalized.split("base64,", 1)[1]
        except IndexError as exc:
            raise ValueError(f"Invalid data URL {field_name} payload") from exc
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("-", "+").replace("_", "/")
    missing_padding = len(normalized) % 4
    if missing_padding:
        normalized += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(normalized, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 {field_name} payload") from exc


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _safe_cache_key_filename(cache_key: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", cache_key)
    if not safe_name.strip(".-"):
        raise ValueError("Invalid kiosk try-on cache key")
    return safe_name


def _require_metadata_string(raw_metadata: dict[str, Any], field_name: str) -> str:
    value = raw_metadata.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing metadata field: {field_name}")
    return value


def _optional_metadata_string(
    raw_metadata: dict[str, Any], field_name: str
) -> str | None:
    value = raw_metadata.get(field_name)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _generator_seed(generator: Any) -> int | None:
    seed = getattr(generator, "seed", None)
    return seed if isinstance(seed, int) else None
