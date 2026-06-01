"""
Privacy-first personalized avatar preview domain helpers.
"""

from src.modules.avatar_preview.profile import (
    AvatarFraming,
    AvatarProfileInput,
    AvatarStyle,
    BasicBodyProfile,
    BodyInputMode,
    DerivedAvatarProfile,
    DetailedBodyProfile,
    FashnVtonCategory,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
    avatar_framing_for_garment_region,
    default_sleeve_length_for_garment_type,
    derive_avatar_profile,
    fashn_vton_category_for_garment,
    report_safe_profile,
    resolve_garment_region,
)
from src.modules.avatar_preview.cache_keys import (
    build_avatar_cache_key,
    build_preview_cache_key,
    derived_profile_hash,
)
from src.modules.avatar_preview.cache_registry import (
    AvatarCacheRegistry,
    CacheArtifactRecord,
)
from src.modules.avatar_preview.prompt_builder import (
    AVATAR_PROMPT_VERSION,
    PREVIEW_CONTEXT_PROMPT_VERSION,
    build_avatar_generation_prompt,
    build_avatar_preview_context_prompt,
)
from src.modules.avatar_preview.tryon_analyzer import (
    ANALYZER_PROMPT_VERSION,
    TryOnIntent,
    build_multimodal_tryon_prompt,
    build_tryon_analyzer_prompt,
    parse_tryon_intent_response,
)

__all__ = [
    "ANALYZER_PROMPT_VERSION",
    "AVATAR_PROMPT_VERSION",
    "AvatarFraming",
    "AvatarProfileInput",
    "AvatarStyle",
    "AvatarCacheRegistry",
    "BasicBodyProfile",
    "BodyInputMode",
    "DerivedAvatarProfile",
    "DetailedBodyProfile",
    "FashnVtonCategory",
    "GarmentRegion",
    "GarmentSleeveLength",
    "GarmentType",
    "CacheArtifactRecord",
    "TryOnIntent",
    "avatar_framing_for_garment_region",
    "PREVIEW_CONTEXT_PROMPT_VERSION",
    "build_avatar_cache_key",
    "build_avatar_generation_prompt",
    "build_avatar_preview_context_prompt",
    "build_multimodal_tryon_prompt",
    "build_tryon_analyzer_prompt",
    "build_preview_cache_key",
    "default_sleeve_length_for_garment_type",
    "derive_avatar_profile",
    "derived_profile_hash",
    "fashn_vton_category_for_garment",
    "parse_tryon_intent_response",
    "report_safe_profile",
    "resolve_garment_region",
]
