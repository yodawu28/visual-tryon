"""
Service layer for avatar-first outfit preview.
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

from src.modules.avatar_preview.cache_registry import (
    AvatarCacheRegistry,
    CacheArtifactRecord,
)
from src.modules.avatar_preview.cache_keys import (
    build_avatar_cache_key,
    build_preview_cache_key,
    preview_context_prompt_hash,
)
from src.modules.avatar_preview.profile import (
    AvatarFraming,
    AvatarPreviewQualityMode,
    AvatarProfileInput,
    DerivedAvatarProfile,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
    avatar_framing_for_garment_region,
    default_sleeve_length_for_garment_type,
    derive_avatar_profile,
    report_safe_profile,
    resolve_garment_region,
)
from src.modules.avatar_preview.prompt_builder import (
    AVATAR_PROMPT_VERSION,
    build_avatar_generation_prompt,
    build_avatar_preview_context_prompt,
)
from src.modules.avatar_preview.tryon_analyzer import (
    TryOnIntent,
    build_multimodal_tryon_prompt,
)


@dataclass(frozen=True)
class AvatarGenerationResult:
    avatar_image: str
    avatar_cache_key: str
    avatar_framing: str
    garment_region: str
    garment_type: str | None
    garment_sleeve_length: str
    cache_hit: bool
    avatar_prompt_version: str
    avatar_path: Path
    metadata_path: Path
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AvatarTryOnResult:
    generated_image: str
    avatar_cache_key: str
    avatar_framing: str
    garment_region: str
    garment_type: str | None
    is_preview: bool
    quality_mode: str
    preview_model: str
    preview_prompt_version: str
    model_warning: str
    generation_time_seconds: float
    preview_cache_key: str
    preview_cache_hit: bool
    preview_path: Path
    preview_metadata_path: Path
    product_scope: str = "avatar_creative_preview"
    baseline_scope: str = "upper_body"
    multimodal_analysis_applied: bool = False
    tryon_intent: dict[str, Any] | None = None
    analyzer_model: str | None = None
    analyzer_prompt_version: str | None = None


@dataclass(frozen=True)
class PreviewCacheEntry:
    cache_key: str
    path: Path
    metadata_path: Path
    cache_hit: bool


class AvatarPreviewService:
    def __init__(
        self,
        *,
        avatar_generator: Any,
        preview_generator: Any,
        tryon_analyzer: Any | None = None,
        avatar_cache_dir: Path,
    ) -> None:
        self.avatar_generator = avatar_generator
        self.preview_generator = preview_generator
        self.tryon_analyzer = tryon_analyzer
        self.avatar_cache_dir = avatar_cache_dir
        self.cache_registry = AvatarCacheRegistry(
            self.avatar_cache_dir / "cache_index.sqlite3"
        )

    def generate_avatar(
        self,
        *,
        profile_input: AvatarProfileInput,
        garment_region: GarmentRegion | None = None,
        garment_type: GarmentType | None = None,
        garment_sleeve_length: GarmentSleeveLength | None = None,
        avatar_framing: AvatarFraming | None = None,
        force_regenerate: bool = False,
    ) -> AvatarGenerationResult:
        derived_profile = derive_avatar_profile(profile_input)
        effective_garment_region = resolve_garment_region(
            garment_type=garment_type,
            garment_region=garment_region,
        )
        avatar_framing = avatar_framing or avatar_framing_for_garment_region(
            effective_garment_region
        )
        effective_sleeve_length = (
            garment_sleeve_length
            or default_sleeve_length_for_garment_type(garment_type)
        )
        raw_metadata = self.avatar_generator.get_runtime_metadata()
        avatar_model = _require_metadata_string(raw_metadata, "avatar_model")
        avatar_catalog_version = _require_metadata_string(
            raw_metadata,
            "avatar_catalog_version",
        )
        avatar_cache_key = build_avatar_cache_key(
            derived_profile=derived_profile,
            avatar_model_id=avatar_model,
            avatar_catalog_version=avatar_catalog_version,
            avatar_framing=avatar_framing,
            garment_region=effective_garment_region,
            garment_type=garment_type,
            garment_sleeve_length=effective_sleeve_length,
        )
        avatar_path = self._avatar_path_for_cache_key(avatar_cache_key)
        metadata_path = self._metadata_path_for_cache_key(avatar_cache_key)
        prompt = build_avatar_generation_prompt(
            derived_profile,
            avatar_framing=avatar_framing,
            garment_region=effective_garment_region,
            garment_sleeve_length=effective_sleeve_length,
        )
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        self.avatar_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_hit = (
            avatar_path.exists() and metadata_path.exists() and not force_regenerate
        )
        if cache_hit:
            avatar_bytes = avatar_path.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.cache_registry.mark_accessed(avatar_cache_key)
        else:
            avatar_b64 = self.avatar_generator.generate_avatar(
                prompt=prompt,
                size="1024x1024",
            )
            avatar_bytes = _decode_base64_payload(avatar_b64, field_name="avatar")
            avatar_path.parent.mkdir(parents=True, exist_ok=True)
            avatar_path.write_bytes(avatar_bytes)
            metadata = {
                "avatar_cache_key": avatar_cache_key,
                "avatar_image_sha256": hashlib.sha256(avatar_bytes).hexdigest(),
                "avatar_model": avatar_model,
                "avatar_catalog_version": avatar_catalog_version,
                "avatar_prompt_version": AVATAR_PROMPT_VERSION,
                "avatar_prompt_sha256": prompt_sha256,
                "avatar_framing": avatar_framing.value,
                "garment_region": effective_garment_region.value,
                "garment_type": garment_type.value if garment_type else None,
                "garment_sleeve_length": effective_sleeve_length.value,
                "derived_profile": derived_profile.model_dump(mode="json"),
                "report_profile": report_safe_profile(profile_input),
                "created_at": datetime.now(UTC).isoformat(),
            }
            metadata_path.write_text(
                json.dumps(metadata, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        self._index_avatar_cache(
            avatar_cache_key=avatar_cache_key,
            avatar_path=avatar_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )

        return AvatarGenerationResult(
            avatar_image=base64.b64encode(avatar_bytes).decode("utf-8"),
            avatar_cache_key=avatar_cache_key,
            avatar_framing=avatar_framing.value,
            garment_region=effective_garment_region.value,
            garment_type=garment_type.value if garment_type else None,
            garment_sleeve_length=effective_sleeve_length.value,
            cache_hit=cache_hit,
            avatar_prompt_version=AVATAR_PROMPT_VERSION,
            avatar_path=avatar_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )

    def get_cached_avatar(self, avatar_cache_key: str) -> AvatarGenerationResult:
        avatar_path = self._avatar_path_for_cache_key(avatar_cache_key)
        metadata_path = self._metadata_path_for_cache_key(avatar_cache_key)
        if not avatar_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Avatar cache key not found: {avatar_cache_key}")

        avatar_bytes = avatar_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self._index_avatar_cache(
            avatar_cache_key=avatar_cache_key,
            avatar_path=avatar_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )
        self.cache_registry.mark_accessed(avatar_cache_key)
        return AvatarGenerationResult(
            avatar_image=base64.b64encode(avatar_bytes).decode("utf-8"),
            avatar_cache_key=avatar_cache_key,
            avatar_framing=str(metadata["avatar_framing"]),
            garment_region=str(metadata["garment_region"]),
            garment_type=metadata.get("garment_type"),
            garment_sleeve_length=str(
                metadata.get("garment_sleeve_length", GarmentSleeveLength.UNKNOWN.value)
            ),
            cache_hit=True,
            avatar_prompt_version=str(metadata["avatar_prompt_version"]),
            avatar_path=avatar_path,
            metadata_path=metadata_path,
            metadata=metadata,
        )

    def try_on_cached_avatar(
        self,
        *,
        avatar_cache_key: str,
        product_image: str,
        quality_mode: AvatarPreviewQualityMode = AvatarPreviewQualityMode.CREATIVE_PREVIEW,
        use_multimodal_analysis: bool = False,
        size: str = "1024x1024",
    ) -> AvatarTryOnResult:
        if quality_mode != AvatarPreviewQualityMode.CREATIVE_PREVIEW:
            raise ValueError("avatar preview only supports creative_preview")

        start_time = time.time()
        avatar_path = self._avatar_path_for_cache_key(avatar_cache_key)
        metadata_path = self._metadata_path_for_cache_key(avatar_cache_key)
        if not avatar_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Avatar cache key not found: {avatar_cache_key}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        derived_profile = DerivedAvatarProfile.model_validate(
            metadata["derived_profile"]
        )
        avatar_framing = AvatarFraming(metadata["avatar_framing"])
        garment_region = GarmentRegion(metadata["garment_region"])
        raw_garment_type = metadata.get("garment_type")
        garment_type = GarmentType(raw_garment_type) if raw_garment_type else None
        avatar_bytes = avatar_path.read_bytes()
        product_bytes = _decode_base64_payload(
            product_image,
            field_name="product_image",
        )
        avatar_b64 = base64.b64encode(avatar_bytes).decode("utf-8")
        product_b64 = base64.b64encode(product_bytes).decode("utf-8")

        tryon_intent: TryOnIntent | None = None
        analyzer_metadata: dict[str, Any] = {}
        if use_multimodal_analysis:
            if self.tryon_analyzer is None:
                raise ValueError("multimodal analysis is not configured")
            analyzer_metadata = self.tryon_analyzer.get_runtime_metadata()
            analyzed_intent = self.tryon_analyzer.analyze_images(
                avatar_image=avatar_bytes,
                garment_image=product_bytes,
            )
            tryon_intent = (
                analyzed_intent
                if isinstance(analyzed_intent, TryOnIntent)
                else TryOnIntent.model_validate(analyzed_intent)
            )
            garment_region = tryon_intent.garment_region
            if tryon_intent.garment_type != GarmentType.UNKNOWN:
                garment_type = tryon_intent.garment_type

        generator = self._generator_for_quality_mode(quality_mode=quality_mode)
        prompt = build_avatar_preview_context_prompt(
            derived_profile,
            avatar_framing=avatar_framing,
            garment_region=garment_region,
            garment_type=garment_type,
        )
        if tryon_intent is not None:
            prompt = build_multimodal_tryon_prompt(
                base_prompt=prompt,
                intent=tryon_intent,
            )
        prompt_sha256 = preview_context_prompt_hash(prompt)
        preview_metadata = generator.get_runtime_metadata()
        preview_model = _require_metadata_string(preview_metadata, "preview_model")
        preview_prompt_version = _require_metadata_string(
            preview_metadata,
            "preview_prompt_version",
        )
        preview_input_mapping = _require_metadata_string(
            preview_metadata,
            "preview_input_mapping",
        )
        preview_cache = self._preview_cache_entry(
            avatar_image_sha256=hashlib.sha256(avatar_bytes).hexdigest(),
            product_image_sha256=hashlib.sha256(product_bytes).hexdigest(),
            prompt_sha256=prompt_sha256,
            preview_model_id=preview_model,
            preview_prompt_version=preview_prompt_version,
            input_mapping=preview_input_mapping,
            seed=_generator_seed(generator),
        )
        if preview_cache.cache_hit:
            generated_bytes = preview_cache.path.read_bytes()
            generated_image = base64.b64encode(generated_bytes).decode("utf-8")
            cached_preview_metadata = json.loads(
                preview_cache.metadata_path.read_text(encoding="utf-8")
            )
            self._index_preview_cache(
                preview_cache_key=preview_cache.cache_key,
                preview_path=preview_cache.path,
                metadata_path=preview_cache.metadata_path,
                metadata=cached_preview_metadata,
            )
            self.cache_registry.mark_accessed(preview_cache.cache_key)
        else:
            generated_image = generator.generate_tryon_from_b64(
                base_image_b64=avatar_b64,
                garment_image_b64=product_b64,
                inpainting_prompt=prompt,
                mask_b64=None,
                size=size,
            )
            generated_bytes = _decode_base64_payload(
                generated_image,
                field_name="generated_image",
            )
            self._write_preview_cache(
                preview_cache=preview_cache,
                generated_bytes=generated_bytes,
                avatar_cache_key=avatar_cache_key,
                avatar_image_sha256=hashlib.sha256(avatar_bytes).hexdigest(),
                product_image_sha256=hashlib.sha256(product_bytes).hexdigest(),
                preview_model=preview_model,
                preview_input_mapping=preview_input_mapping,
                preview_prompt_version=preview_prompt_version,
                prompt_sha256=prompt_sha256,
                quality_mode=quality_mode,
                garment_region=garment_region,
                garment_type=garment_type,
                tryon_intent=tryon_intent,
            )

        return AvatarTryOnResult(
            generated_image=generated_image,
            avatar_cache_key=avatar_cache_key,
            avatar_framing=avatar_framing.value,
            garment_region=garment_region.value,
            garment_type=garment_type.value if garment_type else None,
            is_preview=True,
            quality_mode=quality_mode.value,
            preview_model=preview_model,
            preview_prompt_version=preview_prompt_version,
            model_warning=_model_warning_for_quality_mode(quality_mode),
            generation_time_seconds=time.time() - start_time,
            preview_cache_key=preview_cache.cache_key,
            preview_cache_hit=preview_cache.cache_hit,
            preview_path=preview_cache.path,
            preview_metadata_path=preview_cache.metadata_path,
            multimodal_analysis_applied=tryon_intent is not None,
            tryon_intent=(
                tryon_intent.model_dump(mode="json") if tryon_intent else None
            ),
            analyzer_model=analyzer_metadata.get("model"),
            analyzer_prompt_version=analyzer_metadata.get("analyzer_prompt_version"),
        )

    def get_cached_preview(self, preview_cache_key: str) -> AvatarTryOnResult:
        preview_path = self._preview_path_for_cache_key(preview_cache_key)
        preview_metadata_path = self._preview_metadata_path_for_cache_key(
            preview_cache_key
        )
        if not preview_path.exists() or not preview_metadata_path.exists():
            raise FileNotFoundError(f"Preview cache key not found: {preview_cache_key}")

        generated_bytes = preview_path.read_bytes()
        metadata = json.loads(preview_metadata_path.read_text(encoding="utf-8"))
        avatar = self.get_cached_avatar(str(metadata["avatar_cache_key"]))
        self._index_preview_cache(
            preview_cache_key=preview_cache_key,
            preview_path=preview_path,
            metadata_path=preview_metadata_path,
            metadata=metadata,
        )
        self.cache_registry.mark_accessed(preview_cache_key)

        return AvatarTryOnResult(
            generated_image=base64.b64encode(generated_bytes).decode("utf-8"),
            avatar_cache_key=avatar.avatar_cache_key,
            avatar_framing=avatar.avatar_framing,
            garment_region=str(metadata["garment_region"]),
            garment_type=metadata.get("garment_type"),
            is_preview=True,
            quality_mode=str(metadata["quality_mode"]),
            preview_model=str(metadata["preview_model"]),
            preview_prompt_version=str(metadata["preview_prompt_version"]),
            model_warning=_model_warning_for_quality_mode(
                AvatarPreviewQualityMode(metadata["quality_mode"])
            ),
            generation_time_seconds=0.0,
            preview_cache_key=preview_cache_key,
            preview_cache_hit=True,
            preview_path=preview_path,
            preview_metadata_path=preview_metadata_path,
            multimodal_analysis_applied=bool(
                metadata.get("multimodal_analysis_applied", False)
            ),
            tryon_intent=metadata.get("tryon_intent"),
        )

    def _generator_for_quality_mode(
        self,
        *,
        quality_mode: AvatarPreviewQualityMode,
    ) -> Any:
        if quality_mode == AvatarPreviewQualityMode.CREATIVE_PREVIEW:
            return self.preview_generator
        raise ValueError("avatar preview only supports creative_preview")

    def _avatar_path_for_cache_key(self, avatar_cache_key: str) -> Path:
        return self._artifact_path_for_cache_key(
            cache_key=avatar_cache_key,
            artifact_dir="avatars",
            suffix="png",
        )

    def _metadata_path_for_cache_key(self, avatar_cache_key: str) -> Path:
        return self._artifact_path_for_cache_key(
            cache_key=avatar_cache_key,
            artifact_dir="avatars",
            suffix="json",
        )

    def _preview_path_for_cache_key(self, preview_cache_key: str) -> Path:
        return self._artifact_path_for_cache_key(
            cache_key=preview_cache_key,
            artifact_dir="previews",
            suffix="png",
        )

    def _preview_metadata_path_for_cache_key(self, preview_cache_key: str) -> Path:
        return self._artifact_path_for_cache_key(
            cache_key=preview_cache_key,
            artifact_dir="previews",
            suffix="json",
        )

    def _artifact_path_for_cache_key(
        self,
        *,
        cache_key: str,
        artifact_dir: str,
        suffix: str,
    ) -> Path:
        safe_name = _safe_cache_key_filename(cache_key)
        current_path = self.avatar_cache_dir / artifact_dir / f"{safe_name}.{suffix}"
        legacy_path = self.avatar_cache_dir / f"{safe_name}.{suffix}"
        if legacy_path.exists() and not current_path.exists():
            return legacy_path
        return current_path

    def _preview_cache_entry(
        self,
        *,
        avatar_image_sha256: str,
        product_image_sha256: str,
        prompt_sha256: str,
        preview_model_id: str,
        preview_prompt_version: str,
        input_mapping: str,
        seed: int | None,
    ) -> PreviewCacheEntry:
        cache_key = build_preview_cache_key(
            avatar_image_sha256=avatar_image_sha256,
            product_image_sha256=product_image_sha256,
            preview_context_prompt_sha256=prompt_sha256,
            preview_model_id=preview_model_id,
            preview_prompt_version=preview_prompt_version,
            input_mapping=input_mapping,
            seed=seed,
        )
        path = self._preview_path_for_cache_key(cache_key)
        metadata_path = self._preview_metadata_path_for_cache_key(cache_key)
        return PreviewCacheEntry(
            cache_key=cache_key,
            path=path,
            metadata_path=metadata_path,
            cache_hit=path.exists() and metadata_path.exists(),
        )

    def _write_preview_cache(
        self,
        *,
        preview_cache: PreviewCacheEntry,
        generated_bytes: bytes,
        avatar_cache_key: str,
        avatar_image_sha256: str,
        product_image_sha256: str,
        preview_model: str,
        preview_input_mapping: str,
        preview_prompt_version: str,
        prompt_sha256: str,
        quality_mode: AvatarPreviewQualityMode,
        garment_region: GarmentRegion,
        garment_type: GarmentType | None,
        tryon_intent: TryOnIntent | None,
    ) -> None:
        preview_cache.path.parent.mkdir(parents=True, exist_ok=True)
        preview_cache.path.write_bytes(generated_bytes)
        preview_metadata = {
            "preview_cache_key": preview_cache.cache_key,
            "avatar_cache_key": avatar_cache_key,
            "avatar_image_sha256": avatar_image_sha256,
            "product_image_sha256": product_image_sha256,
            "preview_image_sha256": hashlib.sha256(generated_bytes).hexdigest(),
            "preview_model": preview_model,
            "preview_input_mapping": preview_input_mapping,
            "preview_prompt_version": preview_prompt_version,
            "preview_context_prompt_sha256": prompt_sha256,
            "quality_mode": quality_mode.value,
            "garment_region": garment_region.value,
            "garment_type": garment_type.value if garment_type else None,
            "multimodal_analysis_applied": tryon_intent is not None,
            "tryon_intent": (
                tryon_intent.model_dump(mode="json") if tryon_intent else None
            ),
            "created_at": datetime.now(UTC).isoformat(),
        }
        preview_cache.metadata_path.write_text(
            json.dumps(preview_metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._index_preview_cache(
            preview_cache_key=preview_cache.cache_key,
            preview_path=preview_cache.path,
            metadata_path=preview_cache.metadata_path,
            metadata=preview_metadata,
        )

    def _index_avatar_cache(
        self,
        *,
        avatar_cache_key: str,
        avatar_path: Path,
        metadata_path: Path,
        metadata: dict[str, Any],
    ) -> None:
        self.cache_registry.upsert_artifact(
            CacheArtifactRecord(
                cache_key=avatar_cache_key,
                artifact_kind="avatar",
                image_path=avatar_path,
                metadata_path=metadata_path,
                model=_optional_metadata_string(metadata, "avatar_model"),
                prompt_version=_optional_metadata_string(
                    metadata,
                    "avatar_prompt_version",
                ),
                image_sha256=_optional_metadata_string(
                    metadata,
                    "avatar_image_sha256",
                ),
                metadata={
                    "avatar_framing": metadata.get("avatar_framing"),
                    "garment_region": metadata.get("garment_region"),
                    "garment_type": metadata.get("garment_type"),
                    "garment_sleeve_length": metadata.get("garment_sleeve_length"),
                },
            )
        )

    def _index_preview_cache(
        self,
        *,
        preview_cache_key: str,
        preview_path: Path,
        metadata_path: Path,
        metadata: dict[str, Any],
    ) -> None:
        self.cache_registry.upsert_artifact(
            CacheArtifactRecord(
                cache_key=preview_cache_key,
                artifact_kind="preview",
                image_path=preview_path,
                metadata_path=metadata_path,
                model=_optional_metadata_string(metadata, "preview_model"),
                prompt_version=_optional_metadata_string(
                    metadata,
                    "preview_prompt_version",
                ),
                input_mapping=_optional_metadata_string(
                    metadata,
                    "preview_input_mapping",
                ),
                image_sha256=_optional_metadata_string(
                    metadata,
                    "preview_image_sha256",
                ),
                parent_cache_key=_optional_metadata_string(
                    metadata,
                    "avatar_cache_key",
                ),
                metadata={
                    "quality_mode": metadata.get("quality_mode"),
                    "garment_region": metadata.get("garment_region"),
                    "garment_type": metadata.get("garment_type"),
                    "multimodal_analysis_applied": metadata.get(
                        "multimodal_analysis_applied",
                        False,
                    ),
                },
            )
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


def _safe_cache_key_filename(cache_key: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", cache_key)
    if not safe_name.strip(".-"):
        raise ValueError("Invalid avatar cache key")
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


def _model_warning_for_quality_mode(quality_mode: AvatarPreviewQualityMode) -> str:
    if quality_mode == AvatarPreviewQualityMode.GARMENT_FIDELITY:
        return (
            "Garment-fidelity avatar try-on using a VTON model; exact logo/text "
            "preservation still requires manual review."
        )
    return (
        "Creative avatar preview; not exact virtual try-on, exact fit prediction, "
        "or exact logo/text reproduction."
    )
