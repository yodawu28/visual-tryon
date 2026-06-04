import base64

from src.modules.avatar_preview.profile import (
    AvatarFraming,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)
from src.modules.avatar_preview.tryon_analyzer import TryOnIntent
from src.modules.kiosk_tryon.visual_tryon import KioskVisualTryOnService


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = []
        self.seed = 42

    def get_runtime_metadata(self):
        return {
            "preview_model": "qwen/qwen-image-edit-2511",
            "preview_prompt_version": "qwen-tryon-v1",
            "preview_input_mapping": "multi_image_edit",
        }

    def generate_tryon_from_b64(
        self,
        *,
        base_image_b64,
        garment_image_b64,
        inpainting_prompt,
        mask_b64,
        size,
    ):
        self.calls.append(
            {
                "base_image_b64": base_image_b64,
                "garment_image_b64": garment_image_b64,
                "inpainting_prompt": inpainting_prompt,
                "mask_b64": mask_b64,
                "size": size,
            }
        )
        return base64.b64encode(b"generated-image").decode("utf-8")


class FakeAnalyzer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def get_runtime_metadata(self):
        return {
            "provider": "ollama",
            "model": "qwen2.5vl:7b",
            "analyzer_prompt_version": "avatar-tryon-analyzer-v1",
        }

    def analyze_images(self, *, avatar_image, garment_image):
        self.calls.append((avatar_image, garment_image))
        if self.fail:
            raise ValueError("ollama unavailable")
        return TryOnIntent(
            garment_region=GarmentRegion.UPPER_BODY,
            garment_type=GarmentType.JERSEY,
            sleeve_length=GarmentSleeveLength.SHORT_SLEEVE,
            neckline="v-neck",
            dominant_colors=["mint", "navy"],
            logo_or_text="flag patch",
            pattern="subtle geometric pattern",
            recommended_avatar_framing=AvatarFraming.FULL_BODY,
        )


def test_kiosk_visual_tryon_uses_multimodal_prompt_and_cache(tmp_path):
    generator = FakeGenerator()
    analyzer = FakeAnalyzer()
    service = KioskVisualTryOnService(
        tryon_dir=tmp_path,
        generator=generator,
        tryon_analyzer=analyzer,
    )

    first = service.generate_tryon(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        user_image=b"user-image",
        garment_image=b"garment-image",
        garment_category="tops",
        garment_type="jersey",
    )
    second = service.generate_tryon(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        user_image=b"user-image",
        garment_image=b"garment-image",
        garment_category="tops",
        garment_type="jersey",
    )

    assert first.generated_image == base64.b64encode(b"generated-image").decode("utf-8")
    assert first.personalized_tryon_key.startswith("kiosk-tryon:v1:")
    assert first.multimodal_analysis_applied is True
    assert first.tryon_intent["garment_type"] == "jersey"
    assert "flag patch" in generator.calls[0]["inpainting_prompt"]
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.personalized_tryon_key == first.personalized_tryon_key
    assert len(generator.calls) == 1


def test_kiosk_visual_tryon_falls_back_when_analyzer_fails(tmp_path):
    generator = FakeGenerator()
    service = KioskVisualTryOnService(
        tryon_dir=tmp_path,
        generator=generator,
        tryon_analyzer=FakeAnalyzer(fail=True),
    )

    result = service.generate_tryon(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        user_image=b"user-image",
        garment_image=b"garment-image",
        garment_category="tops",
        garment_type="jersey",
    )

    assert result.multimodal_analysis_applied is False
    assert result.warnings
    assert "deterministic prompt used" in result.warnings[0]
    assert (
        "selected garment category is tops" in generator.calls[0]["inpainting_prompt"]
    )
