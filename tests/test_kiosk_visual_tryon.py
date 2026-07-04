import base64
import json
import shutil

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


class FakeKioskGenerator(FakeGenerator):
    def __init__(self) -> None:
        super().__init__()
        self.last_metadata = {}

    def get_runtime_metadata(self):
        return {
            "preview_model": "Leffa:fake",
            "preview_prompt_version": "local-leffa-category-conditioned-v1",
            "preview_input_mapping": "category_conditioned_leffa",
        }

    def generate_kiosk_tryon(
        self,
        *,
        user_image,
        garment_image,
        prompt,
        garment_category,
        garment_type,
        session_id,
        garment_id,
        size,
    ):
        self.calls.append(
            {
                "user_image": user_image,
                "garment_image": garment_image,
                "prompt": prompt,
                "garment_category": garment_category,
                "garment_type": garment_type,
                "session_id": session_id,
                "garment_id": garment_id,
                "size": size,
            }
        )
        self.last_metadata = {
            "provider": "local_leffa",
            "work_dir": "/workspace/tryon-data/kiosk_tryons/leffa_work/test",
            "conditioned_person": (
                "/workspace/tryon-data/kiosk_tryons/leffa_work/test/"
                "person-conditioned.png"
            ),
            "conditioned_garment": (
                "/workspace/tryon-data/kiosk_tryons/leffa_work/test/"
                "garment-conditioned.png"
            ),
            "leffa_report": (
                "/workspace/tryon-data/kiosk_tryons/leffa_work/test/"
                "leffa-report.json"
            ),
            "warnings": ["input quality gate warning: use upper-body crop"],
        }
        return base64.b64encode(b"leffa-image").decode("utf-8")

    def get_last_generation_metadata(self):
        return self.last_metadata


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
    assert first.output_quality_gate is not None
    assert first.output_quality_gate["status"] == "failed"
    assert second.cache_hit is True
    assert second.personalized_tryon_key == first.personalized_tryon_key
    assert second.output_quality_gate == first.output_quality_gate
    assert second.generation_metadata == {}
    assert second.diagnostic_artifacts == {}
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


def test_kiosk_visual_tryon_recreates_output_dirs_before_writing(tmp_path):
    generator = FakeGenerator()
    service = KioskVisualTryOnService(
        tryon_dir=tmp_path,
        generator=generator,
        tryon_analyzer=None,
    )
    shutil.rmtree(tmp_path / "images")
    shutil.rmtree(tmp_path / "metadata")

    result = service.generate_tryon(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        user_image=b"user-image",
        garment_image=b"garment-image",
        garment_category="tops",
        garment_type="jersey",
        use_multimodal_analysis=False,
    )

    assert result.personalized_tryon_path.exists()
    assert result.metadata_path.exists()
    assert result.generated_image == base64.b64encode(b"generated-image").decode(
        "utf-8"
    )


def test_kiosk_visual_tryon_uses_extended_local_generator_hook(tmp_path):
    generator = FakeKioskGenerator()
    service = KioskVisualTryOnService(
        tryon_dir=tmp_path,
        generator=generator,
        tryon_analyzer=None,
    )

    result = service.generate_tryon(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        user_image=b"user-image",
        garment_image=b"garment-image",
        garment_category="tops",
        garment_type="t-shirt",
        use_multimodal_analysis=False,
        size="768x1024",
    )
    cached = service.generate_tryon(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        user_image=b"user-image",
        garment_image=b"garment-image",
        garment_category="tops",
        garment_type="t-shirt",
        use_multimodal_analysis=False,
        size="768x1024",
    )

    assert result.generated_image == base64.b64encode(b"leffa-image").decode("utf-8")
    assert generator.calls[0]["garment_category"] == "tops"
    assert generator.calls[0]["garment_type"] == "t-shirt"
    assert generator.calls[0]["size"] == "768x1024"
    assert result.input_mapping == "category_conditioned_leffa"
    assert result.generation_metadata["provider"] == "local_leffa"
    assert result.diagnostic_artifacts == {
        "work_dir": "/workspace/tryon-data/kiosk_tryons/leffa_work/test",
        "conditioned_person": (
            "/workspace/tryon-data/kiosk_tryons/leffa_work/test/"
            "person-conditioned.png"
        ),
        "conditioned_garment": (
            "/workspace/tryon-data/kiosk_tryons/leffa_work/test/"
            "garment-conditioned.png"
        ),
        "leffa_report": (
            "/workspace/tryon-data/kiosk_tryons/leffa_work/test/" "leffa-report.json"
        ),
    }
    assert "input quality gate warning: use upper-body crop" in result.warnings
    assert any("output quality gate warning" in item for item in result.warnings)
    metadata = json.loads(result.metadata_path.read_text("utf-8"))
    assert metadata["output_quality_gate"]["status"] == "failed"
    assert metadata["diagnostic_artifacts"] == result.diagnostic_artifacts
    assert cached.cache_hit is True
    assert cached.generation_metadata == result.generation_metadata
    assert cached.diagnostic_artifacts == result.diagnostic_artifacts
