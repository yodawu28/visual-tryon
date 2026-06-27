import pytest

from src.modules.kiosk_tryon.service import KioskTryOnService


class FakeCaptureAnalyzer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze_front_capture(self, image_bytes: bytes):
        self.calls.append(image_bytes)
        return self.result


class FakeCategoryCaptureAnalyzer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze_front_capture(self, image_bytes: bytes, *, garment_category=None):
        self.calls.append(
            {
                "image_bytes": image_bytes,
                "garment_category": garment_category,
            }
        )
        return self.result


class FakeGarmentRegistry:
    def __init__(self, existing_ids):
        self.existing_ids = set(existing_ids)

    def exists(self, garment_id: str) -> bool:
        return garment_id in self.existing_ids


class FakeGarment:
    def __init__(self, category: str):
        self.category = category


class FakeReadableGarmentRegistry(FakeGarmentRegistry):
    def __init__(self, garments):
        super().__init__(existing_ids=set(garments))
        self.garments = garments

    def get_garment(self, garment_id: str):
        return self.garments.get(garment_id)


def test_create_session_persists_avatar_preview_context(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)

    session = service.create_session(
        garment_id="garment-001",
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    assert session.session_id.startswith("kiosk-session:v1:")
    assert session.status == "avatar_preview_ready"
    assert session.garment_id == "garment-001"
    assert session.avatar_cache_key == "avatar:v1:abc"
    assert session.avatar_preview_cache_key == "avatar-preview:v1:def"
    assert session.capture_keys == []
    assert session.personalized_tryon_key is None

    loaded = service.get_session(session.session_id)
    assert loaded == session


def test_create_session_allows_direct_user_capture_flow_without_avatar_preview(
    tmp_path,
):
    service = KioskTryOnService(session_dir=tmp_path)

    session = service.create_session(
        garment_id="garment-001",
    )

    assert session.status == "awaiting_user_capture"
    assert session.garment_id == "garment-001"
    assert session.avatar_cache_key is None
    assert session.avatar_preview_cache_key is None

    loaded = service.get_session(session.session_id)
    assert loaded == session


def test_create_session_rejects_missing_registered_garment(tmp_path):
    service = KioskTryOnService(
        session_dir=tmp_path,
        garment_registry=FakeGarmentRegistry(existing_ids={"garment:v1:known"}),
    )

    with pytest.raises(FileNotFoundError, match="Garment not found"):
        service.create_session(garment_id="garment:v1:missing")


def test_add_user_capture_stores_images_and_updates_session_status(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    updated = service.add_user_capture(
        session_id=session.session_id,
        front_image=b"front-image",
        side_image=b"side-image",
    )

    assert updated.status == "user_captured"
    assert updated.capture_keys == ["front", "side"]
    assert updated.captures["front"]["path"].endswith("-front.png")
    assert updated.captures["side"]["path"].endswith("-side.png")

    front_path = tmp_path / updated.captures["front"]["path"]
    side_path = tmp_path / updated.captures["side"]["path"]
    assert front_path.read_bytes() == b"front-image"
    assert side_path.read_bytes() == b"side-image"

    loaded = service.get_session(session.session_id)
    assert loaded.status == "user_captured"
    assert loaded.capture_keys == ["front", "side"]


def test_analyze_user_capture_marks_session_ready_when_capture_passes(tmp_path):
    analyzer = FakeCaptureAnalyzer(
        {
            "passed": True,
            "score": 0.91,
            "issues": [],
            "guidance": [],
            "checks": {"full_body_visible": True},
        }
    )
    service = KioskTryOnService(session_dir=tmp_path, capture_analyzer=analyzer)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )
    service.add_user_capture(
        session_id=session.session_id,
        front_image=b"front-image",
    )

    updated = service.analyze_user_capture(session_id=session.session_id)

    assert analyzer.calls == [b"front-image"]
    assert updated.status == "capture_analysis_passed"
    assert updated.capture_analysis == {
        "passed": True,
        "score": 0.91,
        "issues": [],
        "guidance": [],
        "checks": {"full_body_visible": True},
    }

    front_bytes = service.read_capture_image(
        session_id=session.session_id,
        capture_key="front",
    )
    assert front_bytes == b"front-image"

    tryon_ready = service.mark_personalized_tryon_ready(
        session_id=session.session_id,
        personalized_tryon_key="kiosk-tryon:v1:abc",
    )
    assert tryon_ready.status == "personalized_tryon_ready"
    assert tryon_ready.personalized_tryon_key == "kiosk-tryon:v1:abc"

    fit_ready = service.mark_fit_analysis_ready(
        session_id=session.session_id,
        fit_analysis_key="kiosk-fit:v1:abc",
    )
    assert fit_ready.status == "fit_analysis_ready"
    assert fit_ready.personalized_tryon_key == "kiosk-tryon:v1:abc"
    assert fit_ready.fit_analysis_key == "kiosk-fit:v1:abc"


def test_capture_source_is_stored_and_added_to_capture_analysis(tmp_path):
    analyzer = FakeCaptureAnalyzer(
        {
            "passed": True,
            "score": 0.91,
            "issues": [],
            "guidance": [],
            "checks": {"full_body_visible": True},
        }
    )
    service = KioskTryOnService(session_dir=tmp_path, capture_analyzer=analyzer)
    session = service.create_session(garment_id=None)

    captured = service.add_user_capture(
        session_id=session.session_id,
        front_image=b"front-image",
        capture_source="Guided Mobile Web",
        capture_metadata={
            "front": {
                "capture_mode": "countdown_scan_burst",
                "burst_count": 5,
                "selected_frame_score": 0.82,
                "selected_frame_metrics": {"brightness": 151.2},
            }
        },
    )
    assert captured.captures["front"]["source"] == "guided_mobile_web"
    assert captured.captures["front"]["metadata"]["selected_frame_score"] == 0.82

    analyzed = service.analyze_user_capture(session_id=session.session_id)

    assert analyzed.capture_analysis is not None
    assert analyzed.capture_analysis["capture_source"] == "guided_mobile_web"
    source_quality = analyzed.capture_analysis["capture_source_quality"]
    assert source_quality["guided_capture"] is True
    assert source_quality["protocol_quality"]["target_confidence_signal"] is True
    assert analyzed.capture_analysis["capture_metadata"]["burst_count"] == 5
    assert (
        "calibrated measurements"
        in source_quality["confidence_policy"]
    )


def test_analyze_user_capture_passes_garment_category_to_analyzer(tmp_path):
    analyzer = FakeCategoryCaptureAnalyzer(
        {
            "passed": True,
            "score": 0.91,
            "issues": [],
            "guidance": [],
            "checks": {"full_body_visible": True},
        }
    )
    registry = FakeReadableGarmentRegistry(
        {"garment:v1:shirt": FakeGarment(category="tops")}
    )
    service = KioskTryOnService(
        session_dir=tmp_path,
        capture_analyzer=analyzer,
        garment_registry=registry,
    )
    session = service.create_session(garment_id="garment:v1:shirt")
    service.add_user_capture(
        session_id=session.session_id,
        front_image=b"front-image",
    )

    updated = service.analyze_user_capture(session_id=session.session_id)

    assert updated.status == "capture_analysis_passed"
    assert analyzer.calls == [
        {
            "image_bytes": b"front-image",
            "garment_category": "tops",
        }
    ]


def test_analyze_user_capture_marks_session_for_recapture_when_capture_fails(tmp_path):
    analyzer = FakeCaptureAnalyzer(
        {
            "passed": False,
            "score": 0.42,
            "issues": ["feet_not_visible", "arms_covering_torso"],
            "guidance": [
                "Step back so full body and feet are visible",
                "Keep arms relaxed and slightly away from torso",
            ],
            "checks": {
                "full_body_visible": False,
                "arms_not_blocking_torso": False,
            },
        }
    )
    service = KioskTryOnService(session_dir=tmp_path, capture_analyzer=analyzer)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )
    service.add_user_capture(
        session_id=session.session_id,
        front_image=b"front-image",
    )

    updated = service.analyze_user_capture(session_id=session.session_id)

    assert updated.status == "needs_recapture"
    assert updated.capture_analysis["passed"] is False
    assert updated.capture_analysis["issues"] == [
        "feet_not_visible",
        "arms_covering_torso",
    ]


def test_analyze_user_capture_requires_front_capture(tmp_path):
    service = KioskTryOnService(
        session_dir=tmp_path,
        capture_analyzer=FakeCaptureAnalyzer({"passed": True}),
    )
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    with pytest.raises(ValueError, match="front capture is required"):
        service.analyze_user_capture(session_id=session.session_id)


def test_read_capture_image_requires_existing_capture(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    with pytest.raises(ValueError, match="side capture is not available"):
        service.read_capture_image(session_id=session.session_id, capture_key="side")


def test_get_session_rejects_unknown_session_id(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)

    with pytest.raises(FileNotFoundError, match="Kiosk session not found"):
        service.get_session("kiosk-session:v1:missing")


def test_add_user_capture_rejects_empty_image_payload(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    with pytest.raises(ValueError, match="front_image must not be empty"):
        service.add_user_capture(
            session_id=session.session_id,
            front_image=b"",
        )
