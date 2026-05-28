"""
Privacy-safe cache key builders for avatar preview artifacts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.modules.avatar_preview.profile import DerivedAvatarProfile
from src.modules.avatar_preview.prompt_builder import (
    AVATAR_PROMPT_VERSION,
    PREVIEW_CONTEXT_PROMPT_VERSION,
)


def derived_profile_hash(profile: DerivedAvatarProfile) -> str:
    payload = profile.model_dump(mode="json")
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def build_avatar_cache_key(
    *,
    derived_profile: DerivedAvatarProfile,
    avatar_model_id: str,
    avatar_catalog_version: str,
) -> str:
    payload = {
        "namespace": "avatar",
        "version": "v1",
        "avatar_prompt_version": AVATAR_PROMPT_VERSION,
        "derived_profile_hash": derived_profile_hash(derived_profile),
        "avatar_model_id": avatar_model_id,
        "avatar_catalog_version": avatar_catalog_version,
        "pose": derived_profile.pose,
    }
    return f"avatar:v1:{_sha256_stable_payload(payload)}"


def build_preview_cache_key(
    *,
    avatar_image_sha256: str,
    product_image_sha256: str,
    preview_model_id: str,
    preview_prompt_version: str,
    input_mapping: str,
    seed: int | None,
) -> str:
    payload = {
        "namespace": "avatar-preview",
        "version": "v1",
        "avatar_image_sha256": avatar_image_sha256,
        "product_image_sha256": product_image_sha256,
        "preview_model_id": preview_model_id,
        "preview_prompt_version": preview_prompt_version,
        "preview_context_prompt_version": PREVIEW_CONTEXT_PROMPT_VERSION,
        "input_mapping": input_mapping,
        "seed": seed,
    }
    return f"avatar-preview:v1:{_sha256_stable_payload(payload)}"


def _sha256_stable_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
