import base64

from src.modules.image_generator.replicate_flux_kontext_generator import (
    ReplicateFluxKontextGenerator,
)


def test_build_inputs_uses_flux_kontext_multi_image_schema():
    generator = ReplicateFluxKontextGenerator.__new__(ReplicateFluxKontextGenerator)
    generator.prompt_variant = "flux-kontext-outfit-preview-v1"
    generator.aspect_ratio = "match_input_image"
    generator.output_format = "png"
    generator.safety_tolerance = 2
    generator.seed = 42

    inputs = generator._build_inputs(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="Black short sleeve t-shirt with red 2026 text",
        mask=None,
    )

    assert inputs["input_image_1"].read() == b"user-image"
    assert inputs["input_image_2"].read() == b"garment-image"
    assert inputs["aspect_ratio"] == "match_input_image"
    assert inputs["output_format"] == "png"
    assert inputs["safety_tolerance"] == 2
    assert inputs["seed"] == 42
    assert "creative outfit preview" in inputs["prompt"]
    assert "Black short sleeve t-shirt with red 2026 text" in inputs["prompt"]


def test_get_runtime_metadata_identifies_flux_kontext_mapping():
    generator = ReplicateFluxKontextGenerator.__new__(ReplicateFluxKontextGenerator)
    generator.model = "flux-kontext-apps/multi-image-kontext-pro"
    generator.model_version = None
    generator.input_mapping = "flux_kontext_multi_image"
    generator.prompt_variant = "flux-kontext-outfit-preview-v1"

    assert generator.get_runtime_metadata() == {
        "preview_model": "flux-kontext-apps/multi-image-kontext-pro",
        "preview_input_mapping": "flux_kontext_multi_image",
        "preview_prompt_version": "flux-kontext-outfit-preview-v1",
    }


def test_generate_tryon_uses_model_name_when_version_is_not_pinned(monkeypatch):
    generator = ReplicateFluxKontextGenerator.__new__(ReplicateFluxKontextGenerator)
    generator.model = "flux-kontext-apps/multi-image-kontext-pro"
    generator.model_version = None
    generator.input_mapping = "flux_kontext_multi_image"
    generator.prompt_variant = "flux-kontext-outfit-preview-v1"
    generator.aspect_ratio = "match_input_image"
    generator.output_format = "png"
    generator.safety_tolerance = 2
    generator.seed = 42

    class FakePrediction:
        id = "prediction-001"
        status = "succeeded"
        output = "https://replicate.delivery/example/output.png"

    class FakePredictionsClient:
        def create(self, *, model, input):
            assert model == "flux-kontext-apps/multi-image-kontext-pro"
            assert input["input_image_1"].read() == b"user-image"
            assert input["input_image_2"].read() == b"garment-image"
            assert "Black t-shirt" in input["prompt"]
            return FakePrediction()

    class FakeClient:
        predictions = FakePredictionsClient()

    class FakeResponse:
        content = b"generated-image"

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout):
        assert url == "https://replicate.delivery/example/output.png"
        assert timeout == 30.0
        return FakeResponse()

    generator.client = FakeClient()
    monkeypatch.setattr(
        "src.modules.image_generator.replicate_flux_kontext_generator.httpx.get",
        fake_get,
    )

    result = generator.generate_tryon(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="Black t-shirt",
    )

    assert result == b"generated-image"


def test_generate_tryon_from_b64_decodes_inputs_and_mask():
    generator = ReplicateFluxKontextGenerator.__new__(ReplicateFluxKontextGenerator)
    user_image = base64.b64encode(b"user-image").decode("utf-8")
    garment_image = base64.b64encode(b"garment-image").decode("utf-8")
    mask_image = base64.b64encode(b"mask-image").decode("utf-8")
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
        inpainting_prompt="Black t-shirt",
        mask_b64=mask_image,
    )

    assert result == base64.b64encode(b"generated-image").decode("utf-8")
    assert captured == {
        "base_image": b"user-image",
        "garment_image": b"garment-image",
        "mask": b"mask-image",
        "prompt": "Black t-shirt",
        "size": "1024x1024",
    }
