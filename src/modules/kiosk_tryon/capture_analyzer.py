"""
Local preflight analysis for kiosk user captures.

The analyzer is intentionally deterministic and cheap. MediaPipe is used only
to produce pose landmarks; pass/fail decisions stay in local scoring logic so
they are testable without loading the MediaPipe model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


PoseEstimator = Callable[[np.ndarray], dict[str, "LandmarkPoint"] | None]


@dataclass(frozen=True)
class LandmarkPoint:
    x: float
    y: float
    visibility: float


@dataclass(frozen=True)
class CaptureAnalysisResult:
    passed: bool
    score: float
    issues: list[str]
    guidance: list[str]
    checks: dict[str, bool]
    metrics: dict[str, float] = field(default_factory=dict)


class KioskCaptureAnalyzer:
    def __init__(
        self,
        *,
        pose_estimator: PoseEstimator,
        min_visibility: float = 0.5,
        min_blur_variance: float = 50.0,
        min_brightness: float = 35.0,
        max_brightness: float = 235.0,
    ) -> None:
        self.pose_estimator = pose_estimator
        self.min_visibility = min_visibility
        self.min_blur_variance = min_blur_variance
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness

    def analyze_front_capture(self, image_bytes: bytes) -> CaptureAnalysisResult:
        image = _decode_image(image_bytes)
        blur_variance = _blur_variance(image)
        brightness = float(np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)))

        checks: dict[str, bool] = {
            "image_not_blurry": blur_variance >= self.min_blur_variance,
            "image_brightness_ok": (
                self.min_brightness <= brightness <= self.max_brightness
            ),
        }
        metrics = {
            "blur_variance": round(blur_variance, 4),
            "brightness": round(brightness, 4),
        }

        landmarks = self.pose_estimator(image)
        if not landmarks:
            checks.update(
                {
                    "person_detected": False,
                    "head_visible": False,
                    "shoulders_visible": False,
                    "hips_visible": False,
                    "knees_visible": False,
                    "ankles_or_feet_visible": False,
                    "full_body_visible": False,
                    "arms_not_blocking_torso": False,
                    "body_centered": False,
                    "front_facing": False,
                }
            )
            return self._result(checks=checks, metrics=metrics)

        pose_checks, pose_metrics = self._score_pose(landmarks)
        checks.update(pose_checks)
        metrics.update(pose_metrics)
        return self._result(checks=checks, metrics=metrics)

    def _score_pose(
        self,
        landmarks: dict[str, LandmarkPoint],
    ) -> tuple[dict[str, bool], dict[str, float]]:
        head_visible = self._visible(landmarks, "nose")
        shoulders_visible = self._visible_pair(
            landmarks, "left_shoulder", "right_shoulder"
        )
        hips_visible = self._visible_pair(landmarks, "left_hip", "right_hip")
        knees_visible = self._visible_pair(landmarks, "left_knee", "right_knee")
        ankles_visible = self._visible_pair(landmarks, "left_ankle", "right_ankle")
        body_centered = self._body_centered(landmarks)
        front_facing_score = self._front_facing_score(landmarks)
        front_facing = front_facing_score >= 0.7

        checks = {
            "person_detected": True,
            "head_visible": head_visible,
            "shoulders_visible": shoulders_visible,
            "hips_visible": hips_visible,
            "knees_visible": knees_visible,
            "ankles_or_feet_visible": ankles_visible,
            "full_body_visible": all(
                [
                    head_visible,
                    shoulders_visible,
                    hips_visible,
                    knees_visible,
                    ankles_visible,
                ]
            ),
            "arms_not_blocking_torso": self._arms_not_blocking_torso(landmarks),
            "body_centered": body_centered,
            "front_facing": front_facing,
        }
        metrics = {
            "front_facing_score": round(front_facing_score, 4),
        }
        return checks, metrics

    def _visible(self, landmarks: dict[str, LandmarkPoint], name: str) -> bool:
        point = landmarks.get(name)
        return point is not None and point.visibility >= self.min_visibility

    def _visible_pair(
        self,
        landmarks: dict[str, LandmarkPoint],
        left_name: str,
        right_name: str,
    ) -> bool:
        return self._visible(landmarks, left_name) and self._visible(
            landmarks, right_name
        )

    def _body_centered(self, landmarks: dict[str, LandmarkPoint]) -> bool:
        visible_points = [
            point for point in landmarks.values() if point.visibility >= self.min_visibility
        ]
        if not visible_points:
            return False
        min_x = min(point.x for point in visible_points)
        max_x = max(point.x for point in visible_points)
        center_x = (min_x + max_x) / 2
        return 0.35 <= center_x <= 0.65 and 0.12 <= (max_x - min_x) <= 0.8

    def _front_facing_score(self, landmarks: dict[str, LandmarkPoint]) -> float:
        required = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]
        if not all(self._visible(landmarks, name) for name in required):
            return 0.0

        left_shoulder = landmarks["left_shoulder"]
        right_shoulder = landmarks["right_shoulder"]
        left_hip = landmarks["left_hip"]
        right_hip = landmarks["right_hip"]

        shoulder_level = max(0.0, 1.0 - abs(left_shoulder.y - right_shoulder.y) * 8)
        hip_level = max(0.0, 1.0 - abs(left_hip.y - right_hip.y) * 8)
        shoulder_width = abs(left_shoulder.x - right_shoulder.x)
        hip_width = abs(left_hip.x - right_hip.x)
        width_score = 1.0 if shoulder_width >= hip_width * 0.8 else 0.4
        return (shoulder_level + hip_level + width_score) / 3

    def _arms_not_blocking_torso(self, landmarks: dict[str, LandmarkPoint]) -> bool:
        required = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]
        if not all(self._visible(landmarks, name) for name in required):
            return False

        left_x = min(landmarks["left_shoulder"].x, landmarks["left_hip"].x)
        right_x = max(landmarks["right_shoulder"].x, landmarks["right_hip"].x)
        top_y = min(landmarks["left_shoulder"].y, landmarks["right_shoulder"].y)
        bottom_y = max(landmarks["left_hip"].y, landmarks["right_hip"].y)

        for wrist_name in ("left_wrist", "right_wrist"):
            wrist = landmarks.get(wrist_name)
            if wrist is None or wrist.visibility < self.min_visibility:
                continue
            if left_x <= wrist.x <= right_x and top_y <= wrist.y <= bottom_y:
                return False
        return True

    def _result(
        self,
        *,
        checks: dict[str, bool],
        metrics: dict[str, float],
    ) -> CaptureAnalysisResult:
        issues = _issues_for_checks(checks)
        guidance = _guidance_for_issues(issues)
        score = round(sum(1 for passed in checks.values() if passed) / len(checks), 4)
        return CaptureAnalysisResult(
            passed=not issues and score >= 0.85,
            score=score,
            issues=issues,
            guidance=guidance,
            checks=checks,
            metrics=metrics,
        )


class MediaPipeKioskCaptureAnalyzer(KioskCaptureAnalyzer):
    def __init__(self, **kwargs: Any) -> None:
        self._pose: Any | None = None
        super().__init__(pose_estimator=self._estimate_pose, **kwargs)

    def _estimate_pose(self, image: np.ndarray) -> dict[str, LandmarkPoint] | None:
        mp = _load_mediapipe()
        if self._pose is None:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
            )

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pose = self._pose
        result = pose.process(rgb_image)
        if not result.pose_landmarks:
            return None

        pose_landmark = mp.solutions.pose.PoseLandmark
        landmarks = result.pose_landmarks.landmark
        return {
            name.lower(): LandmarkPoint(
                x=float(landmarks[getattr(pose_landmark, name).value].x),
                y=float(landmarks[getattr(pose_landmark, name).value].y),
                visibility=float(
                    landmarks[getattr(pose_landmark, name).value].visibility
                ),
            )
            for name in _MEDIAPIPE_LANDMARK_NAMES
        }


_MEDIAPIPE_LANDMARK_NAMES = (
    "NOSE",
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_ELBOW",
    "RIGHT_ELBOW",
    "LEFT_WRIST",
    "RIGHT_WRIST",
    "LEFT_HIP",
    "RIGHT_HIP",
    "LEFT_KNEE",
    "RIGHT_KNEE",
    "LEFT_ANKLE",
    "RIGHT_ANKLE",
)


def _decode_image(image_bytes: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("front_image must be a valid image")
    return image


def _blur_variance(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _issues_for_checks(checks: dict[str, bool]) -> list[str]:
    issues: list[str] = []
    if not checks.get("image_not_blurry", True):
        issues.append("image_blurry")
    if not checks.get("image_brightness_ok", True):
        issues.append("image_brightness_poor")
    if not checks.get("person_detected", True):
        issues.append("person_not_detected")
        return issues
    if not checks.get("head_visible", True):
        issues.append("head_not_visible")
    if not checks.get("shoulders_visible", True):
        issues.append("shoulders_not_visible")
    if not checks.get("hips_visible", True):
        issues.append("hips_not_visible")
    if not checks.get("knees_visible", True):
        issues.append("knees_not_visible")
    if not checks.get("ankles_or_feet_visible", True):
        issues.append("feet_not_visible")
    if not checks.get("arms_not_blocking_torso", True):
        issues.append("arms_covering_torso")
    if not checks.get("body_centered", True):
        issues.append("body_not_centered")
    if not checks.get("front_facing", True):
        issues.append("not_front_facing")
    return issues


def _guidance_for_issues(issues: list[str]) -> list[str]:
    guidance_map = {
        "image_blurry": "Hold still and retake a sharper photo",
        "image_brightness_poor": "Use brighter, even lighting before retaking",
        "person_not_detected": "Stand in front of the camera so your full body is visible",
        "head_not_visible": "Move back so your head is visible",
        "shoulders_not_visible": "Move back so both shoulders are visible",
        "hips_not_visible": "Move back so your hips are visible",
        "knees_not_visible": "Move back so both knees are visible",
        "feet_not_visible": "Step back so full body and feet are visible",
        "arms_covering_torso": "Keep arms relaxed and slightly away from torso",
        "body_not_centered": "Stand centered in the camera frame",
        "not_front_facing": "Face the camera directly",
    }
    return [guidance_map[issue] for issue in issues if issue in guidance_map]


def _load_mediapipe() -> Any:
    try:
        import mediapipe as mp  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "mediapipe is required for kiosk capture analysis; install requirements.txt"
        ) from exc
    return mp
