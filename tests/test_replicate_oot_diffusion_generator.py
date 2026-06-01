import base64

from src.modules.image_generator.replicate_oot_diffusion_generator import (
    ReplicateOotDiffusionGenerator,
)


def test_build_inputs_uses_oot_diffusion_schema():
    generator = ReplicateOotDiffusionGenerator.__new__(ReplicateOotDiffusionGenerator)
    generator.steps = 20
    generator.guidance_scale = 2
    generator.seed = 42

    inputs = generator._build_inputs(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="ignored by OOTDiffusion",
        mask=None,
    )

    assert inputs["model_image"].read() == b"user-image"
    assert inputs["garment_image"].read() == b"garment-image"
    assert inputs["steps"] == 20
    assert inputs["guidance_scale"] == 2
    assert inputs["seed"] == 42


def test_get_runtime_metadata_identifies_oot_diffusion_mapping():
    generator = ReplicateOotDiffusionGenerator.__new__(ReplicateOotDiffusionGenerator)
    generator.model = "viktorfa/oot_diffusion"
    generator.model_version = "9f8fa495"
    generator.input_mapping = "replicate_oot_diffusion"
    generator.prompt_variant = "oot-diffusion-v1"

    assert generator.get_runtime_metadata() == {
        "preview_model": "9f8fa495",
        "preview_input_mapping": "replicate_oot_diffusion",
        "preview_prompt_version": "oot-diffusion-v1",
    }


def test_generate_tryon_accepts_list_output_file_object():
    generator = ReplicateOotDiffusionGenerator.__new__(ReplicateOotDiffusionGenerator)
    generator.model = "viktorfa/oot_diffusion"
    generator.model_version = "9f8fa495"
    generator.input_mapping = "replicate_oot_diffusion"
    generator.prompt_variant = "oot-diffusion-v1"
    generator.steps = 20
    generator.guidance_scale = 2
    generator.seed = 42

    class FakeOutputFile:
        def read(self):
            return b"generated-image"

    class FakePrediction:
        id = "prediction-001"
        status = "succeeded"
        output = [FakeOutputFile()]

    class FakePredictionsClient:
        def create(self, *, version, input):
            assert version == "9f8fa495"
            assert input["model_image"].read() == b"user-image"
            assert input["garment_image"].read() == b"garment-image"
            assert input["steps"] == 20
            assert input["guidance_scale"] == 2
            assert input["seed"] == 42
            return FakePrediction()

    class FakeClient:
        predictions = FakePredictionsClient()

    generator.client = FakeClient()

    result = generator.generate_tryon(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="ignored",
    )

    assert result == b"generated-image"


def test_generate_tryon_from_b64_decodes_optional_mask():
    generator = ReplicateOotDiffusionGenerator.__new__(ReplicateOotDiffusionGenerator)
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
