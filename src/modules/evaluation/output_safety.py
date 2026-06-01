"""
Output safety postprocessing for preview-model evaluation runs.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from src.modules.privacy_guard.face_anonymizer import FaceAnonymizer
from src.modules.privacy_guard.face_detector import FaceDetector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreviewPostprocessResult:
    image_b64: str
    mask_applied: bool
    mask_source: str | None
    face_preserve_applied: bool
    face_preserve_source: str | None


class PreviewOutputSafetyPostprocessor:
    """
    Keep Qwen-style preview outputs inside the intended edit area.

    The eval harness calls generators directly, so it does not get the API route's
    mask and anonymized-face restoration safeguards. This postprocessor mirrors
    that containment for preview mappings known to support multi-image editing.
    """

    def __init__(
        self,
        *,
        face_detector: Any | None = None,
        enabled_input_mappings: set[str] | None = None,
        apply_mask: bool = False,
    ) -> None:
        self._face_detector = face_detector
        self.enabled_input_mappings = enabled_input_mappings or {"multi_image_edit"}
        self.apply_mask = apply_mask

    def __call__(
        self,
        *,
        base_image_b64: str,
        generated_image_b64: str,
        mask_b64: str | None,
        preview_metadata: dict[str, Any | None],
    ) -> PreviewPostprocessResult:
        input_mapping = preview_metadata.get("input_mapping")
        if input_mapping not in self.enabled_input_mappings:
            return PreviewPostprocessResult(
                image_b64=generated_image_b64,
                mask_applied=False,
                mask_source=None,
                face_preserve_applied=False,
                face_preserve_source=None,
            )

        output_image_b64 = generated_image_b64
        mask_applied = False
        mask_source = None

        if self.apply_mask and mask_b64:
            output_image_b64 = _apply_mask_composite(
                base_image_b64=base_image_b64,
                generated_image_b64=output_image_b64,
                mask_b64=mask_b64,
            )
            mask_applied = True
            mask_source = "manifest"

        (
            output_image_b64,
            face_preserve_applied,
            face_preserve_source,
        ) = self._apply_face_preserve_composite(
            base_image_b64=base_image_b64,
            generated_image_b64=output_image_b64,
        )

        return PreviewPostprocessResult(
            image_b64=output_image_b64,
            mask_applied=mask_applied,
            mask_source=mask_source,
            face_preserve_applied=face_preserve_applied,
            face_preserve_source=face_preserve_source,
        )

    @property
    def face_detector(self) -> Any:
        if self._face_detector is None:
            self._face_detector = FaceDetector()
        return self._face_detector

    def _apply_face_preserve_composite(
        self,
        *,
        base_image_b64: str,
        generated_image_b64: str,
    ) -> tuple[str, bool, str | None]:
        base_image = _decode_image_array_from_b64(
            base_image_b64,
            field_name="anonymized_user_image",
            flags=cv2.IMREAD_COLOR,
        )
        generated_image = _decode_image_array_from_b64(
            generated_image_b64,
            field_name="generated_image",
            flags=cv2.IMREAD_COLOR,
        )

        target_h, target_w = base_image.shape[:2]
        if generated_image.shape[:2] != (target_h, target_w):
            logger.warning(
                "Resizing preview output from %s to match base image size %s for face preservation",
                generated_image.shape[:2],
                (target_h, target_w),
            )
            generated_image = cv2.resize(
                generated_image,
                (target_w, target_h),
                interpolation=cv2.INTER_LINEAR,
            )

        faces = self.face_detector.detect_faces(base_image)
        face_bboxes = [tuple(face.bbox.astype(int)) for face in faces]
        face_source = "anonymized base image"

        if not face_bboxes:
            logger.warning(
                "No faces detected on anonymized base image; falling back to generated preview output"
            )
            faces = self.face_detector.detect_faces(generated_image)
            face_bboxes = [tuple(face.bbox.astype(int)) for face in faces]
            face_source = "generated image"

        if not face_bboxes:
            return _encode_image_array_to_b64(generated_image), False, None

        output = generated_image.copy()
        preserved_regions = 0

        for x1, y1, x2, y2 in face_bboxes:
            ex1, ey1, ex2, ey2 = FaceAnonymizer._expand_face_bbox(
                x1,
                y1,
                x2,
                y2,
                target_w,
                target_h,
                privacy_level="standard",
            )

            base_region = base_image[ey1:ey2, ex1:ex2]
            generated_region = output[ey1:ey2, ex1:ex2]
            if base_region.size == 0 or generated_region.size == 0:
                continue

            mask = FaceAnonymizer._create_soft_face_mask(
                width=ex2 - ex1,
                height=ey2 - ey1,
                privacy_level="standard",
            )
            blended = (
                generated_region.astype(np.float32) * (1.0 - mask)
                + base_region.astype(np.float32) * mask
            )
            output[ey1:ey2, ex1:ex2] = np.clip(blended, 0, 255).astype(np.uint8)
            preserved_regions += 1

        logger.info(
            "Applied preview anonymized face preservation to %s region(s) using %s",
            preserved_regions,
            face_source,
        )

        return (
            _encode_image_array_to_b64(output),
            preserved_regions > 0,
            face_source if preserved_regions > 0 else None,
        )


def _decode_base64_payload(payload: str, *, field_name: str) -> bytes:
    if not payload:
        raise ValueError(f"{field_name} payload is empty")

    normalized = payload.strip()
    if normalized.startswith("data:"):
        try:
            normalized = normalized.split("base64,", 1)[1]
        except IndexError as exc:
            raise ValueError(f"Invalid data URL {field_name} payload") from exc

    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("-", "+").replace("_", "/")
    missing_padding = len(normalized) % 4
    if missing_padding:
        normalized += "=" * (4 - missing_padding)

    try:
        return base64.b64decode(normalized, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 {field_name} payload") from exc


def _decode_image_array_from_b64(
    payload: str,
    *,
    field_name: str,
    flags: int,
) -> np.ndarray:
    image_bytes = _decode_base64_payload(payload, field_name=field_name)
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), flags)
    if image is None:
        raise ValueError(
            f"{field_name} must be a supported image (png, jpeg, gif, webp)"
        )
    return image


def _decode_mask_array(mask_b64: str) -> np.ndarray:
    mask = _decode_image_array_from_b64(
        mask_b64,
        field_name="mask",
        flags=cv2.IMREAD_GRAYSCALE,
    )

    if min(mask.shape[:2]) < 8:
        raise ValueError("mask image is too small to be valid")

    return mask


def _encode_image_array_to_b64(image: np.ndarray) -> str:
    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Failed to encode preview postprocessed image")
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _apply_mask_composite(
    *,
    base_image_b64: str,
    generated_image_b64: str,
    mask_b64: str,
) -> str:
    base_image = _decode_image_array_from_b64(
        base_image_b64,
        field_name="anonymized_user_image",
        flags=cv2.IMREAD_COLOR,
    )
    generated_image = _decode_image_array_from_b64(
        generated_image_b64,
        field_name="generated_image",
        flags=cv2.IMREAD_COLOR,
    )
    mask = _decode_mask_array(mask_b64)

    target_h, target_w = base_image.shape[:2]
    if generated_image.shape[:2] != (target_h, target_w):
        logger.warning(
            "Resizing preview output from %s to match base image size %s",
            generated_image.shape[:2],
            (target_h, target_w),
        )
        generated_image = cv2.resize(
            generated_image,
            (target_w, target_h),
            interpolation=cv2.INTER_LINEAR,
        )

    if mask.shape[:2] != (target_h, target_w):
        logger.info(
            "Resizing eval mask from %s to match base image size %s",
            mask.shape[:2],
            (target_h, target_w),
        )
        mask = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

    mask_float = (mask >= 128).astype(np.float32)[..., None]
    coverage = float((mask_float > 0.5).mean())
    logger.info("Applying preview mask composite (coverage=%.3f)", coverage)

    composited = generated_image.astype(np.float32) * mask_float + base_image.astype(
        np.float32
    ) * (1.0 - mask_float)
    composited = np.clip(composited, 0, 255).astype(np.uint8)
    return _encode_image_array_to_b64(composited)
