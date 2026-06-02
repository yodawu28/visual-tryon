import base64

import pytest

from src.modules.kiosk_tryon.service import KioskTryOnService


class FakeCaptureAnalyzer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze_front_capture(self, image_bytes: bytes):
        self.calls.append(image_bytes)
        return self.result


def _image_b64(value: bytes = b"image-bytes") -> str:
    return base64.b64encode(value).decode("utf-8")


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


def test_add_user_capture_stores_images_and_updates_session_status(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    updated = service.add_user_capture(
        session_id=session.session_id,
        front_image=_image_b64(b"front-image"),
        side_image=_image_b64(b"side-image"),
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
        front_image=_image_b64(b"front-image"),
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
        front_image=_image_b64(b"front-image"),
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


def test_get_session_rejects_unknown_session_id(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)

    with pytest.raises(FileNotFoundError, match="Kiosk session not found"):
        service.get_session("kiosk-session:v1:missing")


def test_add_user_capture_rejects_invalid_image_payload(tmp_path):
    service = KioskTryOnService(session_dir=tmp_path)
    session = service.create_session(
        garment_id=None,
        avatar_cache_key="avatar:v1:abc",
        avatar_preview_cache_key="avatar-preview:v1:def",
    )

    with pytest.raises(ValueError, match="front_image must be valid base64"):
        service.add_user_capture(
            session_id=session.session_id,
            front_image="not-base64",
        )
