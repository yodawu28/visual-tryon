import cv2
import numpy as np
import pytest

from src.modules.kiosk_tryon.capture_analyzer import (
    KioskCaptureAnalyzer,
    LandmarkPoint,
    MediaPipeKioskCaptureAnalyzer,
)


def _image_bytes(*, textured: bool = True) -> bytes:
    if textured:
        image = np.zeros((512, 512, 3), dtype=np.uint8)
        for y in range(0, 512, 16):
            color = 230 if (y // 16) % 2 == 0 else 80
            image[y : y + 8, :] = color
        image[:, 200:312] = 180
    else:
        image = np.full((512, 512, 3), 180, dtype=np.uint8)
    success, buffer = cv2.imencode(".png", image)
    assert success
    return buffer.tobytes()


def _good_landmarks() -> dict[str, LandmarkPoint]:
    return {
        "nose": LandmarkPoint(x=0.50, y=0.12, visibility=0.95),
        "left_shoulder": LandmarkPoint(x=0.38, y=0.25, visibility=0.95),
        "right_shoulder": LandmarkPoint(x=0.62, y=0.25, visibility=0.95),
        "left_elbow": LandmarkPoint(x=0.32, y=0.42, visibility=0.90),
        "right_elbow": LandmarkPoint(x=0.68, y=0.42, visibility=0.90),
        "left_wrist": LandmarkPoint(x=0.28, y=0.58, visibility=0.90),
        "right_wrist": LandmarkPoint(x=0.72, y=0.58, visibility=0.90),
        "left_hip": LandmarkPoint(x=0.42, y=0.52, visibility=0.95),
        "right_hip": LandmarkPoint(x=0.58, y=0.52, visibility=0.95),
        "left_knee": LandmarkPoint(x=0.43, y=0.72, visibility=0.95),
        "right_knee": LandmarkPoint(x=0.57, y=0.72, visibility=0.95),
        "left_ankle": LandmarkPoint(x=0.44, y=0.92, visibility=0.95),
        "right_ankle": LandmarkPoint(x=0.56, y=0.92, visibility=0.95),
    }


def test_capture_analyzer_passes_clear_full_body_front_capture():
    analyzer = KioskCaptureAnalyzer(
        pose_estimator=lambda _image: _good_landmarks(),
        min_blur_variance=5.0,
    )

    result = analyzer.analyze_front_capture(_image_bytes())

    assert result.passed is True
    assert result.score >= 0.9
    assert result.issues == []
    assert result.checks["full_body_visible"] is True
    assert result.checks["arms_not_blocking_torso"] is True


def test_capture_analyzer_fails_when_pose_is_missing():
    analyzer = KioskCaptureAnalyzer(
        pose_estimator=lambda _image: None,
        min_blur_variance=5.0,
    )

    result = analyzer.analyze_front_capture(_image_bytes())

    assert result.passed is False
    assert "person_not_detected" in result.issues
    assert "Stand in front of the camera so your full body is visible" in result.guidance


def test_capture_analyzer_fails_when_feet_are_missing_and_arms_cover_torso():
    landmarks = _good_landmarks()
    landmarks["left_ankle"] = LandmarkPoint(x=0.44, y=0.92, visibility=0.1)
    landmarks["right_ankle"] = LandmarkPoint(x=0.56, y=0.92, visibility=0.1)
    landmarks["left_wrist"] = LandmarkPoint(x=0.48, y=0.42, visibility=0.95)
    landmarks["right_wrist"] = LandmarkPoint(x=0.52, y=0.42, visibility=0.95)
    analyzer = KioskCaptureAnalyzer(
        pose_estimator=lambda _image: landmarks,
        min_blur_variance=5.0,
    )

    result = analyzer.analyze_front_capture(_image_bytes())

    assert result.passed is False
    assert "feet_not_visible" in result.issues
    assert "arms_covering_torso" in result.issues
    assert result.checks["full_body_visible"] is False
    assert result.checks["arms_not_blocking_torso"] is False


def test_capture_analyzer_fails_blurry_image_even_when_pose_passes():
    analyzer = KioskCaptureAnalyzer(
        pose_estimator=lambda _image: _good_landmarks(),
        min_blur_variance=5.0,
    )

    result = analyzer.analyze_front_capture(_image_bytes(textured=False))

    assert result.passed is False
    assert "image_blurry" in result.issues
    assert result.checks["image_not_blurry"] is False


def test_mediapipe_analyzer_can_be_constructed_without_loading_model():
    analyzer = MediaPipeKioskCaptureAnalyzer(min_blur_variance=5.0)

    assert isinstance(analyzer, KioskCaptureAnalyzer)


def test_capture_analyzer_rejects_invalid_image_bytes():
    analyzer = KioskCaptureAnalyzer(pose_estimator=lambda _image: _good_landmarks())

    with pytest.raises(ValueError, match="front_image must be a valid image"):
        analyzer.analyze_front_capture(b"not-an-image")
