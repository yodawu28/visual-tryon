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
    quality_gates: dict[str, Any] = field(default_factory=dict)


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

    def analyze_front_capture(
        self,
        image_bytes: bytes,
        *,
        garment_category: str | None = None,
    ) -> CaptureAnalysisResult:
        image = _decode_image(image_bytes)
        blur_variance = _blur_variance(image)
        brightness = float(np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)))
        image_height, image_width = image.shape[:2]

        checks: dict[str, bool] = {
            "image_not_blurry": blur_variance >= self.min_blur_variance,
            "image_brightness_ok": (
                self.min_brightness <= brightness <= self.max_brightness
            ),
        }
        metrics = {
            "blur_variance": round(blur_variance, 4),
            "brightness": round(brightness, 4),
            "image_width_px": float(image_width),
            "image_height_px": float(image_height),
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
            return self._result(
                checks=checks,
                metrics=metrics,
                garment_category=garment_category,
            )

        pose_checks, pose_metrics = self._score_pose(
            landmarks,
            image_width=image_width,
            image_height=image_height,
        )
        checks.update(pose_checks)
        metrics.update(pose_metrics)
        return self._result(
            checks=checks,
            metrics=metrics,
            garment_category=garment_category,
        )

    def _score_pose(
        self,
        landmarks: dict[str, LandmarkPoint],
        *,
        image_width: int,
        image_height: int,
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
        metrics.update(self._pose_ratio_metrics(landmarks))
        metrics.update(
            _pose_pixel_detail_metrics(
                metrics=metrics,
                image_width=image_width,
                image_height=image_height,
            )
        )
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
            point
            for point in landmarks.values()
            if point.visibility >= self.min_visibility
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

    def _pose_ratio_metrics(
        self,
        landmarks: dict[str, LandmarkPoint],
    ) -> dict[str, float]:
        required = [
            "nose",
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip",
            "left_ankle",
            "right_ankle",
        ]
        if not all(self._visible(landmarks, name) for name in required):
            return {}

        nose = landmarks["nose"]
        left_shoulder = landmarks["left_shoulder"]
        right_shoulder = landmarks["right_shoulder"]
        left_hip = landmarks["left_hip"]
        right_hip = landmarks["right_hip"]
        left_ankle = landmarks["left_ankle"]
        right_ankle = landmarks["right_ankle"]

        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_mid_y = (left_hip.y + right_hip.y) / 2
        ankle_mid_y = (left_ankle.y + right_ankle.y) / 2
        body_height_ratio = max(0.0, ankle_mid_y - nose.y)
        shoulder_width_ratio = abs(left_shoulder.x - right_shoulder.x)
        hip_width_ratio = abs(left_hip.x - right_hip.x)
        torso_height_ratio = max(0.0, hip_mid_y - shoulder_mid_y)

        metrics = {
            "body_height_ratio": body_height_ratio,
            "shoulder_width_ratio": shoulder_width_ratio,
            "hip_width_ratio": hip_width_ratio,
            "torso_height_ratio": torso_height_ratio,
        }
        if hip_width_ratio > 0:
            metrics["shoulder_to_hip_ratio"] = shoulder_width_ratio / hip_width_ratio

        return {key: round(value, 4) for key, value in metrics.items()}

    def _result(
        self,
        *,
        checks: dict[str, bool],
        metrics: dict[str, float],
        garment_category: str | None,
    ) -> CaptureAnalysisResult:
        score = round(sum(1 for passed in checks.values() if passed) / len(checks), 4)
        quality_gates = _quality_gates_for_category(
            garment_category=garment_category,
            checks=checks,
            metrics=metrics,
        )
        issues = _issues_for_checks(checks, garment_category=garment_category)
        guidance = _guidance_for_issues(issues)
        passed = _capture_passed_for_category(
            checks=checks,
            issues=issues,
            score=score,
            quality_gates=quality_gates,
        )
        return CaptureAnalysisResult(
            passed=passed,
            score=score,
            issues=issues,
            guidance=guidance,
            checks=checks,
            metrics=metrics,
            quality_gates=quality_gates,
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


def _pose_pixel_detail_metrics(
    *,
    metrics: dict[str, float],
    image_width: int,
    image_height: int,
) -> dict[str, float]:
    shoulder_width_ratio = metrics.get("shoulder_width_ratio")
    torso_height_ratio = metrics.get("torso_height_ratio")
    body_height_ratio = metrics.get("body_height_ratio")

    detail_metrics: dict[str, float] = {}
    if shoulder_width_ratio is not None:
        detail_metrics["estimated_torso_width_px"] = round(
            float(shoulder_width_ratio) * image_width,
            2,
        )
    if torso_height_ratio is not None:
        detail_metrics["estimated_torso_height_px"] = round(
            float(torso_height_ratio) * image_height,
            2,
        )
    if body_height_ratio is not None:
        detail_metrics["estimated_body_height_px"] = round(
            float(body_height_ratio) * image_height,
            2,
        )
        if torso_height_ratio is not None:
            lower_body_ratio = max(
                0.0,
                float(body_height_ratio) - float(torso_height_ratio),
            )
            detail_metrics["estimated_lower_body_height_px"] = round(
                lower_body_ratio * image_height,
                2,
            )
    return detail_metrics


def _quality_gates_for_category(
    *,
    garment_category: str | None,
    checks: dict[str, bool],
    metrics: dict[str, float],
) -> dict[str, Any]:
    category = _normalize_garment_category(garment_category)
    if category is None:
        return {}

    profile = _capture_profile_for_category(category)
    required_checks = profile["required_checks"]
    missing_required = [
        check_name
        for check_name in required_checks
        if not checks.get(check_name, False)
    ]

    detail_checks = _capture_detail_checks_for_category(category, metrics)
    detail_issues = [
        check_name for check_name, passed in detail_checks.items() if not passed
    ]

    if missing_required:
        status = "failed"
    elif detail_issues:
        status = "warning"
    else:
        status = "passed"

    category_quality_score = _category_quality_score(
        required_checks=required_checks,
        detail_checks=detail_checks,
        checks=checks,
    )
    issues = [f"missing_{item}" for item in missing_required] + detail_issues
    visual_preview_ready = status == "passed" and category_quality_score >= 0.9
    return {
        "category_visual_preview": {
            "status": status,
            "garment_category": category,
            "category_quality_score": category_quality_score,
            "target_confidence_ready": visual_preview_ready,
            "visual_preview_ready": visual_preview_ready,
            "recommended_framing": profile["recommended_framing"],
            "required_checks": required_checks,
            "detail_checks": detail_checks,
            "issues": issues,
            "guidance": _category_gate_guidance(category=category, issues=issues),
            "metrics": {
                key: metrics[key]
                for key in sorted(
                    {
                        "estimated_torso_width_px",
                        "estimated_torso_height_px",
                        "estimated_body_height_px",
                        "estimated_lower_body_height_px",
                        "body_height_ratio",
                        "torso_height_ratio",
                        "shoulder_width_ratio",
                    }
                )
                if key in metrics
            },
        }
    }


def _capture_passed_for_category(
    *,
    checks: dict[str, bool],
    issues: list[str],
    score: float,
    quality_gates: dict[str, Any],
) -> bool:
    category_gate = quality_gates.get("category_visual_preview")
    if isinstance(category_gate, dict):
        hard_input_ready = (
            checks.get("image_not_blurry", True)
            and checks.get("image_brightness_ok", True)
            and checks.get("person_detected", True)
        )
        return hard_input_ready and category_gate.get("status") in {
            "passed",
            "warning",
        }
    return not issues and score >= 0.85


def _category_quality_score(
    *,
    required_checks: list[str],
    detail_checks: dict[str, bool],
    checks: dict[str, bool],
) -> float:
    required_total = max(1, len(required_checks))
    required_passed = sum(1 for check_name in required_checks if checks.get(check_name))
    required_score = required_passed / required_total
    if detail_checks:
        detail_score = sum(1 for passed in detail_checks.values() if passed) / len(
            detail_checks
        )
    else:
        detail_score = 1.0
    return round(required_score * 0.7 + detail_score * 0.3, 4)


def _normalize_garment_category(garment_category: str | None) -> str | None:
    if garment_category is None:
        return None
    normalized = garment_category.strip().lower().replace("-", "_")
    if normalized in {"top", "tops", "upper", "upper_body"}:
        return "tops"
    if normalized in {"bottom", "bottoms", "lower", "lower_body", "pants", "shorts"}:
        return "bottoms"
    if normalized in {"one_piece", "one_pieces", "dress", "dresses"}:
        return "one_pieces"
    if normalized in {"full_body", "full_outfit", "outfit"}:
        return "full_outfit"
    return normalized or None


def _capture_profile_for_category(category: str) -> dict[str, Any]:
    if category == "tops":
        return {
            "recommended_framing": "upper_body",
            "required_checks": [
                "person_detected",
                "head_visible",
                "shoulders_visible",
                "hips_visible",
                "arms_not_blocking_torso",
                "body_centered",
                "front_facing",
            ],
        }
    if category == "bottoms":
        return {
            "recommended_framing": "lower_body",
            "required_checks": [
                "person_detected",
                "hips_visible",
                "knees_visible",
                "ankles_or_feet_visible",
                "body_centered",
                "front_facing",
            ],
        }
    return {
        "recommended_framing": "full_body",
        "required_checks": [
            "person_detected",
            "head_visible",
            "shoulders_visible",
            "hips_visible",
            "knees_visible",
            "ankles_or_feet_visible",
            "full_body_visible",
            "body_centered",
            "front_facing",
        ],
    }


def _capture_detail_checks_for_category(
    category: str,
    metrics: dict[str, float],
) -> dict[str, bool]:
    if category == "tops":
        return {
            "torso_detail_enough": (
                metrics.get("estimated_torso_width_px", 0.0) >= 160
                and metrics.get("estimated_torso_height_px", 0.0) >= 180
            )
        }
    if category == "bottoms":
        return {
            "lower_body_detail_enough": (
                metrics.get("estimated_lower_body_height_px", 0.0) >= 320
            )
        }
    return {
        "full_body_detail_enough": (metrics.get("estimated_body_height_px", 0.0) >= 700)
    }


def _category_gate_guidance(*, category: str, issues: list[str]) -> list[str]:
    guidance: list[str] = []
    if category == "tops" and "torso_detail_enough" in issues:
        guidance.append(
            "Use a closer upper-body capture so chest logo, neckline, and sleeve details are clearer."
        )
    if category == "bottoms" and "lower_body_detail_enough" in issues:
        guidance.append(
            "Use a closer lower-body capture so waist, hip, and leg fit can be judged."
        )
    if (
        category in {"one_pieces", "full_outfit"}
        and "full_body_detail_enough" in issues
    ):
        guidance.append(
            "Use a full-body capture with the shopper larger in frame before judging outfit fit."
        )
    for issue in issues:
        if issue.startswith("missing_"):
            check_name = issue.removeprefix("missing_")
            guidance.append(
                f"Retake the capture so {check_name.replace('_', ' ')} passes for this garment category."
            )
    return guidance


def _issues_for_checks(
    checks: dict[str, bool],
    *,
    garment_category: str | None = None,
) -> list[str]:
    issues: list[str] = []
    if not checks.get("image_not_blurry", True):
        issues.append("image_blurry")
    if not checks.get("image_brightness_ok", True):
        issues.append("image_brightness_poor")
    if not checks.get("person_detected", True):
        issues.append("person_not_detected")
        return issues

    relevant_pose_checks = _issue_relevant_pose_checks(garment_category)
    if not checks.get("head_visible", True):
        _append_if_relevant(
            issues, "head_not_visible", "head_visible", relevant_pose_checks
        )
    if not checks.get("shoulders_visible", True):
        _append_if_relevant(
            issues,
            "shoulders_not_visible",
            "shoulders_visible",
            relevant_pose_checks,
        )
    if not checks.get("hips_visible", True):
        _append_if_relevant(
            issues, "hips_not_visible", "hips_visible", relevant_pose_checks
        )
    if not checks.get("knees_visible", True):
        _append_if_relevant(
            issues, "knees_not_visible", "knees_visible", relevant_pose_checks
        )
    if not checks.get("ankles_or_feet_visible", True):
        _append_if_relevant(
            issues,
            "feet_not_visible",
            "ankles_or_feet_visible",
            relevant_pose_checks,
        )
    if not checks.get("arms_not_blocking_torso", True):
        _append_if_relevant(
            issues,
            "arms_covering_torso",
            "arms_not_blocking_torso",
            relevant_pose_checks,
        )
    if not checks.get("body_centered", True):
        _append_if_relevant(
            issues, "body_not_centered", "body_centered", relevant_pose_checks
        )
    if not checks.get("front_facing", True):
        _append_if_relevant(
            issues, "not_front_facing", "front_facing", relevant_pose_checks
        )
    return issues


def _issue_relevant_pose_checks(garment_category: str | None) -> set[str] | None:
    category = _normalize_garment_category(garment_category)
    if category is None:
        return None
    return set(_capture_profile_for_category(category)["required_checks"])


def _append_if_relevant(
    issues: list[str],
    issue: str,
    check_name: str,
    relevant_pose_checks: set[str] | None,
) -> None:
    if relevant_pose_checks is None or check_name in relevant_pose_checks:
        issues.append(issue)


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
        import mediapipe as mp  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "mediapipe is required for kiosk capture analysis; install requirements.txt"
        ) from exc
    return mp
