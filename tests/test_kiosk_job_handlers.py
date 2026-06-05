from dataclasses import replace

from src.modules.jobs.queue import JobRecord
from src.modules.kiosk_tryon.garment_registry import GarmentRecord
from src.modules.kiosk_tryon.job_handlers import KioskVisualPreviewJobHandler
from src.modules.kiosk_tryon.service import KioskTryOnSession


class FakeSessionService:
    def __init__(self) -> None:
        self.session = KioskTryOnSession(
            session_id="kiosk-session:v1:test",
            status="capture_analysis_passed",
            garment_id="garment:v1:test",
            avatar_cache_key=None,
            avatar_preview_cache_key=None,
            capture_keys=["front"],
            captures={"front": {"path": "captures/front.png"}},
            capture_analysis={"passed": True},
            personalized_tryon_key=None,
            fit_analysis_key=None,
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-01T00:00:00+00:00",
        )

    def get_session(self, session_id):
        assert session_id == self.session.session_id
        return self.session

    def read_capture_image(self, *, session_id, capture_key):
        assert session_id == self.session.session_id
        assert capture_key == "front"
        return b"front-image"

    def mark_personalized_tryon_ready(self, *, session_id, personalized_tryon_key):
        assert session_id == self.session.session_id
        self.session = replace(
            self.session,
            status="personalized_tryon_ready",
            personalized_tryon_key=personalized_tryon_key,
        )
        return self.session


class FakeGarmentRegistry:
    def __init__(self) -> None:
        self.record = GarmentRecord(
            garment_id="garment:v1:test",
            name="Mint jersey",
            category="tops",
            garment_type="jersey",
            storage_provider="local",
            storage_uri="data/garments/images/garment-v1-test.png",
            image_sha256="abc123",
            mime_type="image/png",
            size_bytes=12,
            original_filename="jersey.png",
            size_chart_id=None,
            size_chart=[],
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-01T00:00:00+00:00",
        )

    def get_garment(self, garment_id):
        assert garment_id == self.record.garment_id
        return self.record

    def read_image(self, garment_id):
        assert garment_id == self.record.garment_id
        return b"garment-image"


class FakeVisualTryOnService:
    def generate_tryon(
        self,
        *,
        session_id,
        garment_id,
        user_image,
        garment_image,
        garment_category,
        garment_type=None,
        use_multimodal_analysis=True,
        size="1024x1024",
    ):
        assert session_id == "kiosk-session:v1:test"
        assert garment_id == "garment:v1:test"
        assert user_image == b"front-image"
        assert garment_image == b"garment-image"
        assert garment_category == "tops"
        assert garment_type == "jersey"
        assert use_multimodal_analysis is False
        assert size == "1024x1024"
        return {
            "personalized_tryon_key": "kiosk-tryon:v1:test",
            "personalized_tryon_path": "data/kiosk_tryons/images/test.png",
            "metadata_path": "data/kiosk_tryons/metadata/test.json",
            "cache_hit": False,
            "model": "qwen/qwen-image-edit-2511",
            "prompt_version": "qwen-tryon-v1",
            "input_mapping": "multi_image_edit",
            "generation_time_seconds": 1.0,
            "multimodal_analysis_applied": False,
            "warnings": [],
        }


def test_kiosk_visual_preview_job_handler_generates_preview_and_updates_session():
    session_service = FakeSessionService()
    handler = KioskVisualPreviewJobHandler(
        session_service=session_service,
        garment_registry=FakeGarmentRegistry(),
        visual_tryon_service=FakeVisualTryOnService(),
    )
    job = JobRecord(
        job_id="job:v1:test",
        queue_name="gpu.visual_preview",
        job_type="kiosk_visual_preview",
        status="running",
        payload={
            "session_id": "kiosk-session:v1:test",
            "garment_id": "garment:v1:test",
            "use_multimodal_analysis": False,
            "size": "1024x1024",
        },
    )

    result = handler.handle(job)

    assert result["personalized_tryon_key"] == "kiosk-tryon:v1:test"
    assert result["session_status"] == "personalized_tryon_ready"
    assert result["model"] == "qwen/qwen-image-edit-2511"
    assert session_service.session.personalized_tryon_key == "kiosk-tryon:v1:test"


def test_kiosk_visual_preview_job_handler_requires_passed_capture_analysis():
    session_service = FakeSessionService()
    session_service.session = replace(
        session_service.session,
        capture_analysis={"passed": False},
    )
    handler = KioskVisualPreviewJobHandler(
        session_service=session_service,
        garment_registry=FakeGarmentRegistry(),
        visual_tryon_service=FakeVisualTryOnService(),
    )
    job = JobRecord(
        job_id="job:v1:test",
        queue_name="gpu.visual_preview",
        job_type="kiosk_visual_preview",
        status="running",
        payload={
            "session_id": "kiosk-session:v1:test",
            "garment_id": "garment:v1:test",
        },
    )

    try:
        handler.handle(job)
    except ValueError as exc:
        assert "capture analysis must pass" in str(exc)
    else:
        raise AssertionError("Expected failed capture analysis to reject job")
