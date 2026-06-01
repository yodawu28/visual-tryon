import base64
from unittest.mock import Mock

from src.modules.avatar_preview.cache_registry import AvatarCacheRegistry
from src.modules.avatar_preview.service import AvatarPreviewService
from src.modules.avatar_preview.profile import (
    AvatarFraming,
    AvatarPreviewQualityMode,
    AvatarProfileInput,
    BasicBodyProfile,
    BodyInputMode,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)
from src.modules.avatar_preview.tryon_analyzer import TryOnIntent


def _profile_input() -> AvatarProfileInput:
    return AvatarProfileInput(
        input_mode=BodyInputMode.BASIC,
        basic=BasicBodyProfile(
            gender_presentation="male",
            body_build="athletic",
            height_range="tall",
            shoulder_width="broad",
            fit_preference="regular",
            skin_tone="not_specified",
            age_band="adult",
        ),
    )


def _avatar_generator() -> Mock:
    generator = Mock()
    generator.get_runtime_metadata.return_value = {
        "avatar_model": "black-forest-labs/flux-schnell",
        "avatar_catalog_version": "generated-synthetic-person-photo-v1",
        "avatar_prompt_version": "avatar-body-profile-v4",
    }
    generator.generate_avatar.return_value = base64.b64encode(b"avatar-image").decode(
        "utf-8"
    )
    return generator


def _preview_generator() -> Mock:
    generator = Mock()
    generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "avatar-qwen-multimodal-preview-v1",
    }
    generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"preview-image"
    ).decode("utf-8")
    return generator


def _tryon_analyzer() -> Mock:
    analyzer = Mock()
    analyzer.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "qwen2.5vl:7b",
        "analyzer_prompt_version": "avatar-tryon-analyzer-v1",
    }
    analyzer.analyze_images.return_value = TryOnIntent(
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.JERSEY,
        sleeve_length=GarmentSleeveLength.SHORT_SLEEVE,
        neckline="v-neck",
        dominant_colors=["mint green", "navy blue"],
        logo_or_text="Yonex mark and Korea flag patch",
        pattern="subtle geometric tonal pattern",
        risk_notes=["short-sleeve fidelity is important"],
        recommended_avatar_framing=AvatarFraming.FULL_BODY,
    )
    return analyzer


def test_generate_avatar_writes_image_and_metadata(tmp_path):
    avatar_generator = _avatar_generator()
    service = AvatarPreviewService(
        avatar_generator=avatar_generator,
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    result = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
    )

    assert result.cache_hit is False
    assert result.avatar_framing == "upper_body"
    assert result.avatar_image == base64.b64encode(b"avatar-image").decode("utf-8")
    assert result.avatar_cache_key.startswith("avatar:v1:")
    assert result.garment_sleeve_length == "unknown"
    assert result.avatar_path.exists()
    assert result.metadata_path.exists()
    avatar_generator.generate_avatar.assert_called_once()

    metadata = result.metadata
    assert metadata["garment_region"] == "upper_body"
    assert metadata["garment_sleeve_length"] == "unknown"
    assert metadata["avatar_framing"] == "upper_body"
    assert metadata["derived_profile"]["avatar_style"] == "synthetic_person_photo"


def test_generate_avatar_indexes_cache_metadata(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    result = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.JERSEY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    registry = AvatarCacheRegistry(tmp_path / "cache_index.sqlite3")
    record = registry.get_artifact(result.avatar_cache_key)

    assert record is not None
    assert record.artifact_kind == "avatar"
    assert record.image_path == result.avatar_path
    assert record.metadata_path == result.metadata_path
    assert record.model == "black-forest-labs/flux-schnell"
    assert record.prompt_version == "avatar-body-profile-v4"
    assert record.metadata["garment_region"] == "upper_body"
    assert record.metadata["avatar_framing"] == "full_body"


def test_generate_avatar_reuses_cache_without_provider_call(tmp_path):
    avatar_generator = _avatar_generator()
    service = AvatarPreviewService(
        avatar_generator=avatar_generator,
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    first = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
    )
    avatar_generator.generate_avatar.reset_mock()
    second = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
    )

    assert first.avatar_cache_key == second.avatar_cache_key
    assert second.cache_hit is True
    avatar_generator.generate_avatar.assert_not_called()


def test_get_cached_avatar_returns_image_and_metadata_without_provider_call(tmp_path):
    avatar_generator = _avatar_generator()
    service = AvatarPreviewService(
        avatar_generator=avatar_generator,
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )
    generated = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.JERSEY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )
    avatar_generator.generate_avatar.reset_mock()

    cached = service.get_cached_avatar(generated.avatar_cache_key)

    assert cached.avatar_cache_key == generated.avatar_cache_key
    assert cached.avatar_image == generated.avatar_image
    assert cached.cache_hit is True
    assert cached.avatar_framing == "full_body"
    assert cached.garment_region == "upper_body"
    assert cached.garment_type == "jersey"
    assert cached.garment_sleeve_length == "short_sleeve"
    avatar_generator.generate_avatar.assert_not_called()


def test_generate_avatar_separates_full_body_cache(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    upper = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
    )
    lower = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.LOWER_BODY,
    )

    assert upper.avatar_cache_key != lower.avatar_cache_key
    assert upper.avatar_framing == "upper_body"
    assert lower.avatar_framing == "full_body"


def test_generate_avatar_allows_full_body_framing_for_upper_body_garment(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    result = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
    )

    assert avatar.avatar_framing == "full_body"
    assert avatar.garment_region == "upper_body"
    assert avatar.garment_type is None
    assert avatar.garment_sleeve_length == "unknown"
    assert result.avatar_framing == "full_body"
    assert result.garment_region == "upper_body"
    preview_call = service.preview_generator.generate_tryon_from_b64.call_args.kwargs
    assert "upper body of the full-body avatar" in preview_call["inpainting_prompt"]
    assert "lower body garment preview" not in preview_call["inpainting_prompt"]


def test_garment_type_drives_region_metadata_and_prompt(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.SHORTS,
    )
    result = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
    )

    assert avatar.avatar_framing == "full_body"
    assert avatar.garment_region == "lower_body"
    assert avatar.garment_type == "shorts"
    assert avatar.garment_sleeve_length == "unknown"
    assert avatar.metadata["garment_type"] == "shorts"
    assert result.garment_region == "lower_body"
    assert result.garment_type == "shorts"
    preview_call = service.preview_generator.generate_tryon_from_b64.call_args.kwargs
    assert "shorts to the avatar's lower body only" in preview_call["inpainting_prompt"]
    assert (
        "Keep shirt, torso, arms, and shoes unchanged"
        in preview_call["inpainting_prompt"]
    )


def test_try_on_from_cached_avatar_uses_metadata_prompt(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.LOWER_BODY,
    )

    result = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
        size="1024x1024",
    )

    assert result.generated_image == base64.b64encode(b"preview-image").decode("utf-8")
    assert result.avatar_cache_key == avatar.avatar_cache_key
    assert result.avatar_framing == "full_body"
    assert result.garment_region == "lower_body"
    preview_call = service.preview_generator.generate_tryon_from_b64.call_args.kwargs
    assert base64.b64decode(preview_call["base_image_b64"]) == b"avatar-image"
    assert base64.b64decode(preview_call["garment_image_b64"]) == b"product-image"
    assert (
        "lower-body garment to the avatar's lower body only"
        in preview_call["inpainting_prompt"]
    )


def test_try_on_from_cached_avatar_reuses_preview_cache(tmp_path):
    preview_generator = _preview_generator()
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=preview_generator,
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    first = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
    )
    preview_generator.generate_tryon_from_b64.reset_mock()
    second = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
    )

    assert first.preview_cache_hit is False
    assert second.preview_cache_hit is True
    assert second.generated_image == first.generated_image
    assert second.preview_cache_key == first.preview_cache_key
    assert second.preview_path == first.preview_path
    assert second.preview_metadata_path == first.preview_metadata_path
    assert second.preview_path.exists()
    assert second.preview_metadata_path.exists()
    preview_generator.generate_tryon_from_b64.assert_not_called()


def test_try_on_from_cached_avatar_indexes_preview_cache_metadata(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    result = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
    )

    registry = AvatarCacheRegistry(tmp_path / "cache_index.sqlite3")
    record = registry.get_artifact(result.preview_cache_key)

    assert record is not None
    assert record.artifact_kind == "preview"
    assert record.image_path == result.preview_path
    assert record.metadata_path == result.preview_metadata_path
    assert record.parent_cache_key == avatar.avatar_cache_key
    assert record.model == "qwen/qwen-image-edit-2511"
    assert record.prompt_version == "avatar-qwen-multimodal-preview-v1"
    assert record.input_mapping == "multi_image_edit"
    assert record.metadata["quality_mode"] == "creative_preview"


def test_get_cached_preview_returns_image_and_metadata_without_provider_call(tmp_path):
    preview_generator = _preview_generator()
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=preview_generator,
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_region=GarmentRegion.UPPER_BODY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )
    preview = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
    )
    preview_generator.generate_tryon_from_b64.reset_mock()

    cached = service.get_cached_preview(preview.preview_cache_key)

    assert cached.generated_image == preview.generated_image
    assert cached.preview_cache_key == preview.preview_cache_key
    assert cached.preview_cache_hit is True
    assert cached.preview_path == preview.preview_path
    assert cached.preview_metadata_path == preview.preview_metadata_path
    assert cached.avatar_cache_key == avatar.avatar_cache_key
    assert cached.quality_mode == "creative_preview"
    assert cached.preview_model == "qwen/qwen-image-edit-2511"
    assert cached.product_scope == "avatar_creative_preview"
    assert cached.baseline_scope == "upper_body"
    preview_generator.generate_tryon_from_b64.assert_not_called()


def test_garment_fidelity_mode_is_rejected_for_avatar_api_path(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.JERSEY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    try:
        service.try_on_cached_avatar(
            avatar_cache_key=avatar.avatar_cache_key,
            product_image=base64.b64encode(b"product-image").decode("utf-8"),
            quality_mode=AvatarPreviewQualityMode.GARMENT_FIDELITY,
        )
    except ValueError as exc:
        assert "only supports creative_preview" in str(exc)
    else:
        raise AssertionError("Expected garment_fidelity to be rejected")


def test_generate_avatar_uses_short_sleeve_prompt_for_jersey(tmp_path):
    avatar_generator = _avatar_generator()
    service = AvatarPreviewService(
        avatar_generator=avatar_generator,
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.JERSEY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    prompt = avatar_generator.generate_avatar.call_args.kwargs["prompt"]
    assert avatar.garment_sleeve_length == "short_sleeve"
    assert avatar.metadata["garment_sleeve_length"] == "short_sleeve"
    assert "short-sleeve fitted t-shirt" in prompt
    assert "no long sleeves" in prompt
    assert "no layered undershirt" in prompt


def test_generate_avatar_allows_explicit_sleeve_length_override(tmp_path):
    avatar_generator = _avatar_generator()
    service = AvatarPreviewService(
        avatar_generator=avatar_generator,
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )

    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.JERSEY,
        garment_sleeve_length=GarmentSleeveLength.LONG_SLEEVE,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    prompt = avatar_generator.generate_avatar.call_args.kwargs["prompt"]
    assert avatar.garment_sleeve_length == "long_sleeve"
    assert "long-sleeve fitted top" in prompt


def test_multimodal_try_on_uses_analyzer_intent_without_switching_provider(tmp_path):
    preview_generator = _preview_generator()
    analyzer = _tryon_analyzer()
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=preview_generator,
        tryon_analyzer=analyzer,
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.UNKNOWN,
        garment_region=GarmentRegion.UPPER_BODY,
        avatar_framing=AvatarFraming.FULL_BODY,
    )

    result = service.try_on_cached_avatar(
        avatar_cache_key=avatar.avatar_cache_key,
        product_image=base64.b64encode(b"product-image").decode("utf-8"),
        quality_mode=AvatarPreviewQualityMode.CREATIVE_PREVIEW,
        use_multimodal_analysis=True,
    )

    assert result.multimodal_analysis_applied is True
    assert result.quality_mode == "creative_preview"
    assert result.garment_type == "jersey"
    assert result.garment_region == "upper_body"
    assert result.tryon_intent["sleeve_length"] == "short_sleeve"
    assert result.analyzer_model == "qwen2.5vl:7b"
    assert result.product_scope == "avatar_creative_preview"
    assert result.baseline_scope == "upper_body"
    assert "logo/text" in result.model_warning
    analyzer.analyze_images.assert_called_once_with(
        avatar_image=b"avatar-image",
        garment_image=b"product-image",
    )
    preview_call = preview_generator.generate_tryon_from_b64.call_args.kwargs
    assert "short_sleeve" in preview_call["inpainting_prompt"]
    assert "Yonex mark and Korea flag patch" in preview_call["inpainting_prompt"]
    assert "subtle geometric tonal pattern" in preview_call["inpainting_prompt"]


def test_multimodal_try_on_requires_configured_analyzer(tmp_path):
    service = AvatarPreviewService(
        avatar_generator=_avatar_generator(),
        preview_generator=_preview_generator(),
        avatar_cache_dir=tmp_path,
    )
    avatar = service.generate_avatar(
        profile_input=_profile_input(),
        garment_type=GarmentType.JERSEY,
    )

    try:
        service.try_on_cached_avatar(
            avatar_cache_key=avatar.avatar_cache_key,
            product_image=base64.b64encode(b"product-image").decode("utf-8"),
            use_multimodal_analysis=True,
        )
    except ValueError as exc:
        assert "multimodal analysis is not configured" in str(exc)
    else:
        raise AssertionError("Expected multimodal analysis to require analyzer")
