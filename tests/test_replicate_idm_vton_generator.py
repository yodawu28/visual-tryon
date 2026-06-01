import base64

from src.modules.image_generator.replicate_idm_vton_generator import (
    ReplicateIdmVtonGenerator,
)


def test_build_inputs_uses_idm_vton_schema():
    generator = ReplicateIdmVtonGenerator.__new__(ReplicateIdmVtonGenerator)
    generator.crop = True
    generator.steps = 30
    generator.seed = 42
    generator.category = "upper_body"
    generator.use_mask = False

    inputs = generator._build_inputs(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="Black short sleeve t-shirt with red 2026 text",
        mask=None,
    )

    assert inputs["human_img"].read() == b"user-image"
    assert inputs["garm_img"].read() == b"garment-image"
    assert inputs["garment_des"] == "Black short sleeve t-shirt with red 2026 text"
    assert inputs["category"] == "upper_body"
    assert inputs["crop"] is True
    assert inputs["steps"] == 30
    assert inputs["seed"] == 42
    assert "mask_img" not in inputs


def test_build_inputs_includes_mask_only_when_enabled():
    generator = ReplicateIdmVtonGenerator.__new__(ReplicateIdmVtonGenerator)
    generator.crop = False
    generator.steps = 25
    generator.seed = 7
    generator.category = "auto"
    generator.use_mask = True

    inputs = generator._build_inputs(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="A long evening dress",
        mask=b"mask-image",
    )

    assert inputs["category"] == "dresses"
    assert inputs["mask_img"].read() == b"mask-image"
    assert inputs["crop"] is False
    assert inputs["steps"] == 25
    assert inputs["seed"] == 7


def test_get_runtime_metadata_identifies_idm_vton_mapping():
    generator = ReplicateIdmVtonGenerator.__new__(ReplicateIdmVtonGenerator)
    generator.model = "cuuupid/idm-vton"
    generator.model_version = "pinned-version"
    generator.input_mapping = "replicate_idm_vton"
    generator.prompt_variant = "idm-vton-v1"

    assert generator.get_runtime_metadata() == {
        "preview_model": "pinned-version",
        "preview_input_mapping": "replicate_idm_vton",
        "preview_prompt_version": "idm-vton-v1",
    }


def test_generate_tryon_accepts_string_output_url(monkeypatch):
    generator = ReplicateIdmVtonGenerator.__new__(ReplicateIdmVtonGenerator)
    generator.model = "cuuupid/idm-vton"
    generator.model_version = "0513734"
    generator.input_mapping = "replicate_idm_vton"
    generator.prompt_variant = "idm-vton-v1"
    generator.crop = True
    generator.steps = 30
    generator.seed = 42
    generator.category = "upper_body"
    generator.use_mask = False

    class FakePrediction:
        id = "prediction-001"
        status = "succeeded"
        output = "https://replicate.delivery/example/output.jpg"

    class FakePredictionsClient:
        def create(self, *, version, input):
            assert version == "0513734"
            assert input["human_img"].read() == b"user-image"
            assert input["garm_img"].read() == b"garment-image"
            assert input["category"] == "upper_body"
            return FakePrediction()

    class FakeClient:
        predictions = FakePredictionsClient()

    class FakeResponse:
        content = b"generated-image"

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout):
        assert url == "https://replicate.delivery/example/output.jpg"
        assert timeout == 30.0
        return FakeResponse()

    generator.client = FakeClient()
    monkeypatch.setattr(
        "src.modules.image_generator.replicate_idm_vton_generator.httpx.get",
        fake_get,
    )

    result = generator.generate_tryon(
        base_image=b"user-image",
        garment_image=b"garment-image",
        inpainting_prompt="Black t-shirt",
    )

    assert result == b"generated-image"


def test_generate_tryon_from_b64_passes_optional_mask():
    generator = ReplicateIdmVtonGenerator.__new__(ReplicateIdmVtonGenerator)
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
