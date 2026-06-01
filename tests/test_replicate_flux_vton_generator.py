import base64

from src.modules.image_generator.replicate_flux_vton_generator import (
    ReplicateFluxVtonGenerator,
)


def test_build_inputs_uses_flux_vton_schema():
    generator = ReplicateFluxVtonGenerator.__new__(ReplicateFluxVtonGenerator)
    generator.part = "upper_body"

    inputs = generator._build_inputs(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="ignored by Flux-VTON",
        mask=None,
    )

    assert inputs["image"].read() == b"user-image"
    assert inputs["garment"].read() == b"garment-image"
    assert inputs["part"] == "upper_body"


def test_get_runtime_metadata_identifies_flux_vton_mapping():
    generator = ReplicateFluxVtonGenerator.__new__(ReplicateFluxVtonGenerator)
    generator.model = "subhash25rawat/flux-vton"
    generator.model_version = "a02643ce"
    generator.input_mapping = "replicate_flux_vton"
    generator.prompt_variant = "flux-vton-v1"

    assert generator.get_runtime_metadata() == {
        "preview_model": "a02643ce",
        "preview_input_mapping": "replicate_flux_vton",
        "preview_prompt_version": "flux-vton-v1",
    }


def test_generate_tryon_accepts_string_output_url(monkeypatch):
    generator = ReplicateFluxVtonGenerator.__new__(ReplicateFluxVtonGenerator)
    generator.model = "subhash25rawat/flux-vton"
    generator.model_version = "a02643ce"
    generator.input_mapping = "replicate_flux_vton"
    generator.prompt_variant = "flux-vton-v1"
    generator.part = "upper_body"

    class FakePrediction:
        id = "prediction-001"
        status = "succeeded"
        output = "https://replicate.delivery/example/output.png"

    class FakePredictionsClient:
        def create(self, *, version, input):
            assert version == "a02643ce"
            assert input["image"].read() == b"user-image"
            assert input["garment"].read() == b"garment-image"
            assert input["part"] == "upper_body"
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
        "src.modules.image_generator.replicate_flux_vton_generator.httpx.get",
        fake_get,
    )

    result = generator.generate_tryon(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="ignored",
    )

    assert result == b"generated-image"


def test_generate_tryon_from_b64_passes_optional_mask_without_using_it():
    generator = ReplicateFluxVtonGenerator.__new__(ReplicateFluxVtonGenerator)
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
        inpainting_prompt="ignored",
        mask_b64=mask_image,
    )

    assert result == base64.b64encode(b"generated-image").decode("utf-8")
    assert captured == {
        "base_image": b"user-image",
        "garment_image": b"garment-image",
        "mask": b"mask-image",
        "prompt": "ignored",
        "size": "1024x1024",
    }
