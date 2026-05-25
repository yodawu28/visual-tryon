"""
Tests for the Qwen fast preview generator.
"""

import base64

import pytest

from src.modules.image_generator.replicate_preview_generator import (
    ReplicatePreviewGenerator,
)
from src.modules.image_generator.qwen_fast_generator import QwenFastGenerator


def test_replicate_preview_prompt_version_is_stable():
    generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)

    assert generator.get_preview_prompt_version() == "preview-garment-swap-v1"


class TestQwenFastGenerator:
    def test_build_preview_prompt_references_both_inputs(self):
        prompt = QwenFastGenerator._build_preview_prompt(
            "Place the shirt on the user naturally."
        )

        assert "Edit only the first image." in prompt
        assert "Use the second image only as a garment reference." in prompt
        assert "same anonymized person" in prompt
        assert "original camera texture" in prompt
        assert "Do not beautify" in prompt
        assert "Do not create a new person" in prompt
        assert (
            "If uncertain, keep the first image unchanged except for the clothing swap."
            in prompt
        )
        assert "Place the shirt on the user naturally." not in prompt

    def test_detect_target_region_for_lower_body(self):
        target_region = QwenFastGenerator._detect_target_region(
            "A pair of blue jeans with realistic folds."
        )

        assert target_region == "lower body clothing"

    def test_detect_target_region_for_dress(self):
        target_region = QwenFastGenerator._detect_target_region(
            "A long evening dress with satin fabric."
        )

        assert target_region == "full outfit"

    def test_detect_target_region_for_jersey(self):
        target_region = QwenFastGenerator._detect_target_region(
            "A sports jersey with short sleeves and team logos."
        )

        assert target_region == "upper body clothing"

    def test_decode_base64_image_accepts_data_url_and_missing_padding(self):
        raw = base64.b64encode(b"fake-image-bytes").decode("utf-8").rstrip("=")
        payload = f"data:image/png;base64,\n{raw}"

        decoded = QwenFastGenerator._decode_base64_image(payload)

        assert decoded == b"fake-image-bytes"

    def test_generate_tryon_from_b64_ignores_mask_payload(self):
        generator = QwenFastGenerator.__new__(QwenFastGenerator)
        user_image = base64.b64encode(b"user-image").decode("utf-8")
        garment_image = base64.b64encode(b"garment-image").decode("utf-8")
        ignored_mask = "data:image/png;base64,not-valid-mask"

        captured = {}

        def fake_generate_tryon(
            *,
            base_image: bytes,
            garment_image: bytes,
            inpainting_prompt: str,
            mask: bytes | None,
            size: str,
        ) -> bytes:
            captured["base_image"] = base_image
            captured["garment_image"] = garment_image
            captured["mask"] = mask
            captured["prompt"] = inpainting_prompt
            captured["size"] = size
            return b"generated-image"

        generator.generate_tryon = fake_generate_tryon

        result = generator.generate_tryon_from_b64(
            base_image_b64=user_image,
            garment_image_b64=garment_image,
            inpainting_prompt="Swap shirt",
            mask_b64=ignored_mask,
            size="1024x1024",
        )

        assert result == base64.b64encode(b"generated-image").decode("utf-8")
        assert captured["base_image"] == b"user-image"
        assert captured["garment_image"] == b"garment-image"
        assert captured["mask"] is None
        assert captured["prompt"] == "Swap shirt"
        assert captured["size"] == "1024x1024"


class TestReplicatePreviewGenerator:
    def test_build_inputs_uses_configurable_multi_image_mapping(self):
        generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
        generator.input_mapping = "multi_image_edit"
        generator.go_fast = False

        inputs = generator._build_inputs(
            base_image=b"user-image",
            garment_image=b"garment-image",
            inpainting_prompt="A sports jersey with short sleeves",
        )

        assert inputs["image"][0].read() == b"user-image"
        assert inputs["image"][1].read() == b"garment-image"
        assert inputs["go_fast"] is False
        assert inputs["aspect_ratio"] == "match_input_image"
        assert "Edit only the first image." in inputs["prompt"]

    def test_build_inputs_supports_google_nano_banana_mapping(self):
        generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
        generator.input_mapping = "google_nano_banana"
        generator.go_fast = True

        inputs = generator._build_inputs(
            base_image=b"user-image",
            garment_image=b"garment-image",
            inpainting_prompt="A short sleeve jersey",
        )

        assert inputs["image_input"][0].read() == b"user-image"
        assert inputs["image_input"][1].read() == b"garment-image"
        assert inputs["aspect_ratio"] == "match_input_image"
        assert inputs["output_format"] == "png"
        assert "Edit only the first image." in inputs["prompt"]
        assert "go_fast" not in inputs

    def test_get_runtime_metadata_includes_mapping_and_prompt_version(self):
        generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
        generator.model = "google/nano-banana"
        generator.model_version = None
        generator.input_mapping = "google_nano_banana"

        assert generator.get_runtime_metadata() == {
            "preview_model": "google/nano-banana",
            "preview_input_mapping": "google_nano_banana",
            "preview_prompt_version": "preview-garment-swap-v1",
        }

    def test_get_model_identifier_prefers_version_for_pinned_models(self):
        generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
        generator.model = "owner/model-name"
        generator.model_version = "pinned-version"

        assert generator.get_model_identifier() == "pinned-version"

    def test_get_model_identifier_falls_back_to_model_slug(self):
        generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
        generator.model = "owner/model-name"
        generator.model_version = None

        assert generator.get_model_identifier() == "owner/model-name"


def test_replicate_preview_prompt_variant_defaults_to_current_version():
    generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
    generator.model = "qwen/qwen-image-edit-2511"
    generator.model_version = None
    generator.input_mapping = "multi_image_edit"
    generator.prompt_variant = "preview-garment-swap-v1"

    assert generator.get_runtime_metadata()["preview_prompt_version"] == (
        "preview-garment-swap-v1"
    )


def test_replicate_preview_prompt_variant_v2_emphasizes_garment_preservation():
    generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
    generator.prompt_variant = "preview-garment-preserve-v2"

    prompt = generator._build_configured_preview_prompt(
        "A red jersey with white collar and chest logo"
    )

    assert "Preserve the exact garment color palette" in prompt
    assert "logos, patches, text, stripes" in prompt
    assert "preview-garment-preserve-v2" == generator.get_preview_prompt_version()


def test_replicate_preview_rejects_unknown_prompt_variant():
    generator = ReplicatePreviewGenerator.__new__(ReplicatePreviewGenerator)
    generator.prompt_variant = "missing-variant"

    with pytest.raises(ValueError, match="Unsupported preview prompt variant"):
        generator._build_configured_preview_prompt("A blue hoodie")
