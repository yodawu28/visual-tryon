import pytest

from src.modules.image_generator.replicate_synthetic_avatar_generator import (
    ReplicateSyntheticAvatarGenerator,
)


def _generator() -> ReplicateSyntheticAvatarGenerator:
    generator = ReplicateSyntheticAvatarGenerator.__new__(
        ReplicateSyntheticAvatarGenerator
    )
    generator.model = "black-forest-labs/flux-schnell"
    generator.model_version = None
    generator.avatar_catalog_version = "generated-synthetic-person-photo-v1"
    generator.aspect_ratio = "1:1"
    generator.output_format = "png"
    generator.safety_tolerance = 2
    generator.seed = 42
    return generator


def test_build_inputs_uses_photorealistic_human_avatar_prompt_controls():
    generator = _generator()

    inputs = generator._build_inputs(
        "photorealistic synthetic human model, natural skin texture, not a cartoon"
    )

    assert inputs == {
        "prompt": (
            "photorealistic synthetic human model, natural skin texture, "
            "not a cartoon"
        ),
        "aspect_ratio": "1:1",
        "output_format": "png",
        "safety_tolerance": 2,
        "seed": 42,
    }


def test_empty_avatar_prompt_raises_value_error():
    generator = _generator()

    with pytest.raises(ValueError, match="Avatar generation prompt is empty"):
        generator._build_inputs("  ")


def test_get_runtime_metadata_returns_avatar_generation_defaults():
    generator = _generator()

    assert generator.get_runtime_metadata() == {
        "avatar_model": "black-forest-labs/flux-schnell",
        "avatar_catalog_version": "generated-synthetic-person-photo-v1",
        "avatar_prompt_version": "avatar-body-profile-v4",
    }
