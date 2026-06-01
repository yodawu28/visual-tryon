"""
Avatar-first outfit preview API endpoints.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.config.settings import get_settings
from src.modules.avatar_preview.service import AvatarPreviewService
from src.modules.image_generator.replicate_avatar_preview_generator import (
    ReplicateAvatarPreviewGenerator,
)
from src.modules.image_generator.local_command_avatar_generator import (
    LocalCommandAvatarGenerator,
)
from src.modules.image_generator.replicate_synthetic_avatar_generator import (
    ReplicateSyntheticAvatarGenerator,
)
from src.modules.avatar_preview.tryon_analyzer import OllamaTryOnAnalyzer
from src.modules.product_ingestion.image_fetcher import ProductImageFetcher
from src.schemas.requests import AvatarPreviewAvatarRequest, AvatarPreviewTryOnRequest
from src.schemas.responses import (
    AvatarPreviewAvatarResponse,
    AvatarPreviewTryOnResponse,
)

router = APIRouter(prefix="/api/v1/avatar-preview", tags=["avatar-preview"])


@lru_cache
def get_avatar_preview_service() -> AvatarPreviewService:
    settings = get_settings()
    return AvatarPreviewService(
        avatar_generator=_build_avatar_generator(settings.avatar_generator_mode),
        preview_generator=ReplicateAvatarPreviewGenerator(),
        tryon_analyzer=OllamaTryOnAnalyzer(
            model=settings.tryon_analyzer_ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.tryon_analyzer_timeout,
        ),
        avatar_cache_dir=settings.temp_storage_dir / "avatar_cache",
    )


def _build_avatar_generator(mode: str) -> Any:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "local_command":
        return LocalCommandAvatarGenerator()
    if normalized_mode == "replicate":
        return ReplicateSyntheticAvatarGenerator()
    raise ValueError(f"Unsupported AVATAR_GENERATOR_MODE: {mode}")


@router.post("/avatars", response_model=AvatarPreviewAvatarResponse)
async def generate_avatar(
    request: AvatarPreviewAvatarRequest,
    service: AvatarPreviewService = Depends(get_avatar_preview_service),
) -> AvatarPreviewAvatarResponse:
    try:
        result = service.generate_avatar(
            profile_input=request.body_profile,
            garment_region=request.garment_region,
            garment_type=request.garment_type,
            garment_sleeve_length=request.garment_sleeve_length,
            avatar_framing=request.avatar_framing,
            force_regenerate=request.force_regenerate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _avatar_response(result)


@router.get("/avatars/{avatar_cache_key}", response_model=AvatarPreviewAvatarResponse)
async def get_cached_avatar(
    avatar_cache_key: str,
    service: AvatarPreviewService = Depends(get_avatar_preview_service),
) -> AvatarPreviewAvatarResponse:
    try:
        result = service.get_cached_avatar(avatar_cache_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _avatar_response(result)


@router.post("/try-on", response_model=AvatarPreviewTryOnResponse)
async def try_on_cached_avatar(
    request: AvatarPreviewTryOnRequest,
    service: AvatarPreviewService = Depends(get_avatar_preview_service),
) -> AvatarPreviewTryOnResponse:
    try:
        product_image = await _resolve_product_image(request)
        result = service.try_on_cached_avatar(
            avatar_cache_key=request.avatar_cache_key,
            product_image=product_image,
            quality_mode=request.quality_mode,
            use_multimodal_analysis=request.use_multimodal_analysis,
            size=request.size,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _tryon_response(
        result,
        message="Avatar preview generated successfully",
    )


@router.get("/previews/{preview_cache_key}", response_model=AvatarPreviewTryOnResponse)
async def get_cached_preview(
    preview_cache_key: str,
    service: AvatarPreviewService = Depends(get_avatar_preview_service),
) -> AvatarPreviewTryOnResponse:
    try:
        result = service.get_cached_preview(preview_cache_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _tryon_response(
        result,
        message="Avatar preview loaded from cache",
    )


def _avatar_response(result: Any) -> AvatarPreviewAvatarResponse:
    payload = _result_to_dict(result)
    return AvatarPreviewAvatarResponse(
        success=True,
        avatar_image=payload.get("avatar_image"),
        avatar_cache_key=str(payload["avatar_cache_key"]),
        avatar_framing=str(payload["avatar_framing"]),
        garment_region=str(payload["garment_region"]),
        garment_type=payload.get("garment_type"),
        garment_sleeve_length=payload.get("garment_sleeve_length"),
        cache_hit=bool(payload["cache_hit"]),
        avatar_prompt_version=str(payload["avatar_prompt_version"]),
        avatar_path=_stringify_path(payload["avatar_path"]),
        metadata_path=_stringify_path(payload["metadata_path"]),
        message=(
            "Avatar loaded from cache"
            if payload["cache_hit"]
            else "Avatar generated successfully"
        ),
    )


def _tryon_response(result: Any, *, message: str) -> AvatarPreviewTryOnResponse:
    payload = _result_to_dict(result)
    return AvatarPreviewTryOnResponse(
        success=True,
        generated_image=payload.get("generated_image"),
        avatar_cache_key=str(payload["avatar_cache_key"]),
        avatar_framing=str(payload["avatar_framing"]),
        garment_region=str(payload["garment_region"]),
        garment_type=payload.get("garment_type"),
        is_preview=bool(payload["is_preview"]),
        quality_mode=str(payload["quality_mode"]),
        preview_model=str(payload["preview_model"]),
        preview_prompt_version=str(payload["preview_prompt_version"]),
        model_warning=str(payload["model_warning"]),
        generation_time_seconds=payload.get("generation_time_seconds"),
        preview_cache_key=payload.get("preview_cache_key"),
        preview_cache_hit=bool(payload.get("preview_cache_hit", False)),
        preview_path=(
            _stringify_path(payload["preview_path"])
            if payload.get("preview_path") is not None
            else None
        ),
        preview_metadata_path=(
            _stringify_path(payload["preview_metadata_path"])
            if payload.get("preview_metadata_path") is not None
            else None
        ),
        product_scope=str(payload.get("product_scope", "avatar_creative_preview")),
        baseline_scope=str(payload.get("baseline_scope", "upper_body")),
        multimodal_analysis_applied=bool(
            payload.get("multimodal_analysis_applied", False)
        ),
        tryon_intent=payload.get("tryon_intent"),
        analyzer_model=payload.get("analyzer_model"),
        analyzer_prompt_version=payload.get("analyzer_prompt_version"),
        message=message,
    )


async def _resolve_product_image(request: AvatarPreviewTryOnRequest) -> str:
    if request.product_image:
        return request.product_image
    if request.image_url:
        fetched = await ProductImageFetcher().fetch_image_from_url(request.image_url)
        return fetched.image_base64
    raise ValueError("Either product_image or image_url is required")


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if is_dataclass(result) and not isinstance(result, type):
        return dict(vars(result))
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    raise TypeError(f"Unsupported avatar preview result type: {type(result)}")


def _stringify_path(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)
