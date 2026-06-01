import pytest

from src.modules.image_generator.replicate_avatar_preview_generator import (
    ReplicateAvatarPreviewGenerator,
)


def _generator() -> ReplicateAvatarPreviewGenerator:
    generator = ReplicateAvatarPreviewGenerator.__new__(ReplicateAvatarPreviewGenerator)
    generator.model = "qwen/qwen-image-edit-2511"
    generator.model_version = None
    generator.input_mapping = "multi_image_edit"
    generator.prompt_variant = "avatar-qwen-multimodal-preview-v1"
    generator.go_fast = True
    generator.output_format = "png"
    generator.seed = 42
    return generator


def test_build_inputs_uses_qwen_multi_image_schema_and_passes_avatar_prompt():
    generator = _generator()
    avatar_context_prompt = (
        "Use the first image as a personalized avatar mannequin, not as a real "
        "user photo. Apply the black short sleeve t-shirt from the second image."
    )

    inputs = generator._build_inputs(
        base_image=b"avatar-image",
        garment_image=b"garment-image",
        inpainting_prompt=avatar_context_prompt,
        mask=None,
    )

    assert inputs["image"][0].read() == b"avatar-image"
    assert inputs["image"][0].name == "avatar.png"
    assert inputs["image"][1].read() == b"garment-image"
    assert inputs["image"][1].name == "garment.png"
    assert "personalized avatar mannequin" in inputs["prompt"]
    assert "not as a real user photo" in inputs["prompt"]
    assert "Edit only the first image" not in inputs["prompt"]
    assert inputs["aspect_ratio"] == "match_input_image"
    assert inputs["go_fast"] is True
    assert inputs["output_format"] == "png"
    assert inputs["seed"] == 42


def test_get_runtime_metadata_returns_avatar_preview_defaults():
    generator = _generator()

    assert generator.get_runtime_metadata() == {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "avatar-qwen-multimodal-preview-v1",
    }


def test_invalid_prompt_variant_raises_value_error():
    generator = _generator()
    generator.prompt_variant = "preview-garment-swap-v1"

    with pytest.raises(ValueError, match="Unsupported avatar preview prompt variant"):
        generator.get_prompt_version()
