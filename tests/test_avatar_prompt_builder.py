import src.modules.avatar_preview.cache_keys as cache_keys_module
from src.modules.avatar_preview.cache_keys import (
    build_avatar_cache_key,
    build_preview_cache_key,
    derived_profile_hash,
    preview_context_prompt_hash,
)
from src.modules.avatar_preview.profile import (
    AvatarFraming,
    AvatarProfileInput,
    BodyInputMode,
    DerivedAvatarProfile,
    DetailedBodyProfile,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
    derive_avatar_profile,
)
from src.modules.avatar_preview.prompt_builder import (
    AVATAR_PROMPT_VERSION,
    PREVIEW_CONTEXT_PROMPT_VERSION,
    build_avatar_generation_prompt,
    build_avatar_preview_context_prompt,
)


def _derived_profile() -> DerivedAvatarProfile:
    return DerivedAvatarProfile(
        avatar_style="synthetic_person_photo",
        gender_presentation="male",
        body_build="athletic",
        height_range="tall",
        shoulder_width="broad",
        fit_preference="regular",
        pose="front_relaxed",
        skin_tone="medium",
        age_band="adult",
    )


def _detailed_profile_input() -> AvatarProfileInput:
    return AvatarProfileInput(
        input_mode=BodyInputMode.DETAILED,
        detailed=DetailedBodyProfile(
            gender_presentation="male",
            height_cm=182,
            weight_kg=84,
            shoulder_width_cm=49,
            chest_or_bust_cm=104,
            waist_cm=86,
            hip_cm=98,
            fit_preference="regular",
            pose="front_relaxed",
            skin_tone="medium",
            age_band="adult",
        ),
    )


def test_avatar_generation_prompt_is_non_identifying():
    prompt = build_avatar_generation_prompt(_derived_profile())

    assert AVATAR_PROMPT_VERSION == "avatar-body-profile-v4"
    assert "photorealistic synthetic human model" in prompt
    assert "natural skin texture" in prompt
    assert "not a cartoon" in prompt
    assert "not an illustration" in prompt
    assert "not a plastic mannequin" in prompt
    assert "non-identifying" in prompt
    assert "softly blurred" in prompt
    assert "no recognizable facial details" in prompt
    assert "athletic" in prompt
    assert "broad shoulders" in prompt
    assert "Do not create a face resembling a real person" in prompt


def test_avatar_generation_prompt_supports_full_body_framing():
    prompt = build_avatar_generation_prompt(
        _derived_profile(),
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    assert "full-body" in prompt
    assert "head to shoes" in prompt
    assert "legs fully visible" in prompt
    assert "plain neutral shorts" in prompt


def test_avatar_generation_prompt_supports_short_sleeve_full_body_base():
    prompt = build_avatar_generation_prompt(
        _derived_profile(),
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
        garment_sleeve_length=GarmentSleeveLength.SHORT_SLEEVE,
    )

    assert "short-sleeve fitted t-shirt" in prompt
    assert "bare forearms visible" in prompt
    assert "no long sleeves" in prompt
    assert "no layered undershirt" in prompt


def test_avatar_preview_context_prompt_mentions_body_profile_not_raw_measurements():
    prompt = build_avatar_preview_context_prompt(_derived_profile())

    assert PREVIEW_CONTEXT_PROMPT_VERSION == "avatar-garment-preview-context-v4"
    assert "Edit only the first image" in prompt
    assert "not a side-by-side comparison" in prompt
    assert "photorealistic synthetic human avatar" in prompt
    assert "not a stick figure" in prompt
    assert "not a cartoon" in prompt
    assert "not a mannequin" in prompt
    assert "tall" in prompt
    assert "athletic" in prompt
    assert "broad shoulders" in prompt
    assert "84" not in prompt
    assert "182" not in prompt


def test_avatar_preview_context_prompt_supports_full_body_framing():
    prompt = build_avatar_preview_context_prompt(
        _derived_profile(),
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.LOWER_BODY,
        garment_type=GarmentType.PANTS,
    )

    assert "full-body synthetic human avatar" in prompt
    assert "pants to the avatar's lower body only" in prompt
    assert "legs and hips visible" in prompt
    assert "Keep shirt, torso, arms, and shoes unchanged" in prompt


def test_avatar_preview_context_prompt_supports_upper_body_garment_on_full_body_avatar():
    prompt = build_avatar_preview_context_prompt(
        _derived_profile(),
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.JERSEY,
    )

    assert "full-body synthetic human avatar" in prompt
    assert "sports jersey to the upper body of the full-body avatar only" in prompt
    assert "lower body garment preview" not in prompt
    assert "Keep the legs and lower-body clothing visible and stable" in prompt


def test_avatar_preview_context_prompt_supports_full_outfit_garment_type():
    prompt = build_avatar_preview_context_prompt(
        _derived_profile(),
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.FULL_BODY,
        garment_type=GarmentType.SET,
    )

    assert "matching top and bottom set" in prompt
    assert "full outfit preview" in prompt
    assert "torso, hips, and legs visible" in prompt


def test_derived_profile_hash_is_stable_and_cache_safe():
    derived = _derived_profile()

    first_hash = derived_profile_hash(derived)
    second_hash = derived_profile_hash(derived)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_cache_keys_do_not_include_raw_measurements():
    derived = derive_avatar_profile(_detailed_profile_input())
    preview_context_prompt = build_avatar_preview_context_prompt(derived)

    avatar_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.UPPER_BODY,
    )
    preview_key = build_preview_cache_key(
        avatar_image_sha256="a" * 64,
        product_image_sha256="b" * 64,
        preview_context_prompt_sha256=preview_context_prompt_hash(
            preview_context_prompt
        ),
        preview_model_id="flux-kontext-apps/multi-image-kontext-pro",
        preview_prompt_version="flux-kontext-outfit-preview-v1",
        input_mapping="flux_kontext_multi_image",
        seed=42,
    )
    avatar_prompt = build_avatar_generation_prompt(derived)

    serialized_prompts = f"{avatar_prompt} {preview_context_prompt}"
    serialized_keys = f"{avatar_key} {preview_key}"
    for raw_field_name in (
        "height_cm",
        "weight_kg",
        "shoulder_width_cm",
        "chest_or_bust_cm",
        "waist_cm",
        "hip_cm",
    ):
        assert raw_field_name not in serialized_prompts
        assert raw_field_name not in serialized_keys
    for raw_value in ("182", "84", "104"):
        assert raw_value not in serialized_prompts
    assert avatar_key.startswith("avatar:v1:")
    assert preview_key.startswith("avatar-preview:v1:")


def test_avatar_cache_key_changes_with_avatar_framing():
    derived = derive_avatar_profile(_detailed_profile_input())

    upper_body_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.UPPER_BODY,
    )
    full_body_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    assert full_body_key != upper_body_key


def test_avatar_cache_key_changes_with_garment_region():
    derived = derive_avatar_profile(_detailed_profile_input())

    upper_garment_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
    )
    full_outfit_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.FULL_BODY,
    )

    assert upper_garment_key != full_outfit_key


def test_avatar_cache_key_changes_with_garment_type():
    derived = derive_avatar_profile(_detailed_profile_input())

    shirt_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.SHIRT,
    )
    jersey_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.JERSEY,
    )

    assert shirt_key != jersey_key


def test_avatar_cache_key_changes_with_garment_sleeve_length():
    derived = derive_avatar_profile(_detailed_profile_input())

    short_sleeve_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.JERSEY,
        garment_sleeve_length=GarmentSleeveLength.SHORT_SLEEVE,
    )
    long_sleeve_key = build_avatar_cache_key(
        derived_profile=derived,
        avatar_model_id="local-avatar-catalog",
        avatar_catalog_version="manual-v1",
        avatar_framing=AvatarFraming.FULL_BODY,
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.JERSEY,
        garment_sleeve_length=GarmentSleeveLength.LONG_SLEEVE,
    )

    assert short_sleeve_key != long_sleeve_key


def test_preview_cache_key_changes_with_preview_context_prompt_version(monkeypatch):
    first_key = build_preview_cache_key(
        avatar_image_sha256="a" * 64,
        product_image_sha256="b" * 64,
        preview_context_prompt_sha256="c" * 64,
        preview_model_id="flux-kontext-apps/multi-image-kontext-pro",
        preview_prompt_version="flux-kontext-outfit-preview-v1",
        input_mapping="flux_kontext_multi_image",
        seed=42,
    )

    monkeypatch.setattr(
        cache_keys_module,
        "PREVIEW_CONTEXT_PROMPT_VERSION",
        "avatar-garment-preview-context-v5",
    )
    second_key = build_preview_cache_key(
        avatar_image_sha256="a" * 64,
        product_image_sha256="b" * 64,
        preview_context_prompt_sha256="c" * 64,
        preview_model_id="flux-kontext-apps/multi-image-kontext-pro",
        preview_prompt_version="flux-kontext-outfit-preview-v1",
        input_mapping="flux_kontext_multi_image",
        seed=42,
    )

    assert second_key != first_key


def test_preview_cache_key_changes_with_preview_context_prompt_hash():
    first_key = build_preview_cache_key(
        avatar_image_sha256="a" * 64,
        product_image_sha256="b" * 64,
        preview_context_prompt_sha256=preview_context_prompt_hash(
            "Use the first image as a personalized avatar mannequin."
        ),
        preview_model_id="flux-kontext-apps/multi-image-kontext-pro",
        preview_prompt_version="flux-kontext-outfit-preview-v1",
        input_mapping="flux_kontext_multi_image",
        seed=42,
    )
    second_key = build_preview_cache_key(
        avatar_image_sha256="a" * 64,
        product_image_sha256="b" * 64,
        preview_context_prompt_sha256=preview_context_prompt_hash(
            "Use the first image as a different personalized avatar mannequin."
        ),
        preview_model_id="flux-kontext-apps/multi-image-kontext-pro",
        preview_prompt_version="flux-kontext-outfit-preview-v1",
        input_mapping="flux_kontext_multi_image",
        seed=42,
    )

    assert second_key != first_key
