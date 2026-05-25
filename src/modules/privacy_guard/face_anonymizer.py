"""
Face anonymization through face swapping với AI-generated neutral face.
"""

import insightface
import cv2
import numpy as np
from typing import Optional, List, Literal
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FaceAnonymizer:
    """
    Swap detected faces với neutral AI-generated face.
    """

    def __init__(self, model_path: Optional[Path] = None):
        # Load inswapper model
        if model_path is None:
            # Auto-download to ~/.insightface/models/
            try:
                self.swapper = insightface.model_zoo.get_model(
                    "inswapper_128.onnx", download=True, download_zip=True
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load inswapper model: {e}. Will use fallback anonymization."
                )
                self.swapper = None
        else:
            self.swapper = insightface.model_zoo.get_model(str(model_path))

        # Load or generate neutral face
        self.neutral_face = self._load_neutral_face()

    def _load_neutral_face(self):
        """
        Load pre-generated neutral face embedding.
        Trong production, nên có sẵn một bộ neutral faces.
        """
        # TODO: Implement neutral face library
        # Có thể sử dụng StyleGAN2 hoặc pre-generated faces
        # Hiện tại return None, sẽ use fallback anonymization
        return None

    def anonymize(
        self,
        image: np.ndarray,
        faces: List,
        source_face=None,
        privacy_level: Literal["standard", "strong", "extreme"] = "standard",
    ) -> np.ndarray:
        """
        Swap all faces trong image với neutral face.

        Args:
            image: Original image (BGR)
            faces: List of detected faces from FaceDetector
            source_face: Optional neutral face (nếu None, sẽ tự generate)
            privacy_level: standard = stronger face-only anonymization,
                strong = broader anonymization including more hair/head contour
                and nearby accessories around the face,
                extreme = maximum anonymization over a larger head/neck region

        Returns:
            Anonymized image (BGR)
        """
        if not faces:
            return image.copy()

        result = image.copy()

        if privacy_level in {"strong", "extreme"}:
            return self._fallback_anonymize(result, faces, privacy_level=privacy_level)

        # Nếu không có swapper hoặc neutral face, dùng fallback
        if self.swapper is None or (source_face is None and self.neutral_face is None):
            return self._fallback_anonymize(result, faces, privacy_level=privacy_level)

        source = source_face or self.neutral_face

        try:
            for face in faces:
                result = self.swapper.get(
                    result,
                    face,  # Target face to replace
                    source,  # Neutral face identity
                    paste_back=True,
                )
        except Exception as e:
            logger.error(f"Face swapping failed: {e}. Using fallback.")
            return self._fallback_anonymize(
                image.copy(),
                faces,
                privacy_level=privacy_level,
            )

        return result

    def _fallback_anonymize(
        self,
        image: np.ndarray,
        faces: List,
        privacy_level: Literal["standard", "strong", "extreme"] = "standard",
    ) -> np.ndarray:
        """
        Fallback nếu face swapping fail: expanded low-detail anonymization.

        The fallback intentionally covers more than the exact face bbox so that
        forehead, jawline, ears, and part of the hairline are also anonymized.
        """
        result = image.copy()

        for face in faces:
            try:
                # Get bbox coordinates
                x1, y1, x2, y2 = face.bbox.astype(int)

                # Ensure coordinates are within image bounds
                h, w = result.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                ex1, ey1, ex2, ey2 = self._expand_face_bbox(
                    x1,
                    y1,
                    x2,
                    y2,
                    w,
                    h,
                    privacy_level=privacy_level,
                )
                expanded_region = result[ey1:ey2, ex1:ex2]

                if expanded_region.size == 0:
                    continue

                anonymized_patch = self._create_low_detail_patch(
                    expanded_region,
                    privacy_level=privacy_level,
                )
                mask = self._create_soft_face_mask(
                    width=ex2 - ex1,
                    height=ey2 - ey1,
                    privacy_level=privacy_level,
                )

                blended = (
                    expanded_region.astype(np.float32) * (1.0 - mask)
                    + anonymized_patch.astype(np.float32) * mask
                )
                result[ey1:ey2, ex1:ex2] = blended.astype(np.uint8)

            except Exception as e:
                logger.error(f"Failed to anonymize face: {e}")
                continue

        return result

    @staticmethod
    def _expand_face_bbox(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        image_width: int,
        image_height: int,
        privacy_level: Literal["standard", "strong", "extreme"] = "standard",
    ) -> tuple[int, int, int, int]:
        face_width = x2 - x1
        face_height = y2 - y1

        if privacy_level == "extreme":
            expand_left = int(face_width * 0.8)
            expand_right = int(face_width * 0.8)
            expand_top = int(face_height * 1.15)
            expand_bottom = int(face_height * 1.0)
        elif privacy_level == "strong":
            expand_left = int(face_width * 0.55)
            expand_right = int(face_width * 0.55)
            expand_top = int(face_height * 0.85)
            expand_bottom = int(face_height * 0.65)
        else:
            expand_left = int(face_width * 0.35)
            expand_right = int(face_width * 0.35)
            expand_top = int(face_height * 0.55)
            expand_bottom = int(face_height * 0.35)

        ex1 = max(0, x1 - expand_left)
        ey1 = max(0, y1 - expand_top)
        ex2 = min(image_width, x2 + expand_right)
        ey2 = min(image_height, y2 + expand_bottom)
        return ex1, ey1, ex2, ey2

    @staticmethod
    def _create_low_detail_patch(
        region: np.ndarray,
        privacy_level: Literal["standard", "strong", "extreme"] = "standard",
    ) -> np.ndarray:
        region_h, region_w = region.shape[:2]

        # Heavy pixelation removes high-frequency identity details.
        if privacy_level == "extreme":
            downsample_w = max(4, region_w // 40)
            downsample_h = max(4, region_h // 40)
        elif privacy_level == "strong":
            downsample_w = max(6, region_w // 28)
            downsample_h = max(6, region_h // 28)
        else:
            downsample_w = max(8, region_w // 18)
            downsample_h = max(8, region_h // 18)
        pixelated_small = cv2.resize(
            region,
            (downsample_w, downsample_h),
            interpolation=cv2.INTER_LINEAR,
        )
        pixelated = cv2.resize(
            pixelated_small,
            (region_w, region_h),
            interpolation=cv2.INTER_NEAREST,
        )

        if privacy_level == "extreme":
            blur_kernel = max(31, min(221, ((max(region_w, region_h) * 2 // 3) | 1)))
        elif privacy_level == "strong":
            blur_kernel = max(21, min(181, ((max(region_w, region_h) // 2) | 1)))
        else:
            blur_kernel = max(9, min(151, ((max(region_w, region_h) // 3) | 1)))
        blurred = cv2.GaussianBlur(pixelated, (blur_kernel, blur_kernel), 0)

        mean_color = region.reshape(-1, 3).mean(axis=0).astype(np.uint8)
        flat_patch = np.full_like(region, mean_color)

        if privacy_level == "extreme":
            ultra_flat_patch = (
                flat_patch.astype(np.float32) * 0.96 + blurred.astype(np.float32) * 0.04
            )
            return np.clip(ultra_flat_patch, 0, 255).astype(np.uint8)

        if privacy_level == "strong":
            # Strong mode intentionally removes nearly all original face texture.
            # Add only coarse low-frequency variation so the result does not look like
            # a hard box while still being much harder to recognize.
            coarse_noise = np.random.normal(
                loc=0.0,
                scale=3.0,
                size=(max(4, region_h // 24), max(4, region_w // 24), 3),
            ).astype(np.float32)
            coarse_noise = cv2.resize(
                coarse_noise,
                (region_w, region_h),
                interpolation=cv2.INTER_CUBIC,
            )
            strong_patch = (
                flat_patch.astype(np.float32) * 0.9 + blurred.astype(np.float32) * 0.1
            )
            strong_patch = np.clip(strong_patch + coarse_noise, 0, 255)
            return strong_patch.astype(np.uint8)

        return cv2.addWeighted(blurred, 0.35, flat_patch, 0.65, 0)

    @staticmethod
    def _create_soft_face_mask(
        width: int,
        height: int,
        privacy_level: Literal["standard", "strong", "extreme"] = "standard",
    ) -> np.ndarray:
        mask = np.zeros((height, width), dtype=np.uint8)
        center = (width // 2, height // 2)
        if privacy_level == "extreme":
            axes = (max(1, int(width * 0.72)), max(1, int(height * 0.82)))
            center = (width // 2, int(height * 0.56))
        elif privacy_level == "strong":
            axes = (max(1, int(width * 0.62)), max(1, int(height * 0.7)))
            center = (width // 2, int(height * 0.54))
        else:
            axes = (max(1, int(width * 0.48)), max(1, int(height * 0.5)))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)

        if privacy_level in {"strong", "extreme"}:
            if privacy_level == "extreme":
                rect_top = max(0, int(height * 0.38))
                rect_bottom = min(height, int(height * 1.0))
                rect_left = max(0, int(width * 0.1))
                rect_right = min(width, int(width * 0.9))
            else:
                rect_top = max(0, int(height * 0.48))
                rect_bottom = min(height, int(height * 0.96))
                rect_left = max(0, int(width * 0.18))
                rect_right = min(width, int(width * 0.82))
            cv2.rectangle(
                mask,
                (rect_left, rect_top),
                (rect_right, rect_bottom),
                255,
                -1,
            )

        if privacy_level == "extreme":
            feather_base = 4
        elif privacy_level == "strong":
            feather_base = 5
        else:
            feather_base = 6
        feather_kernel = max(11, min(151, ((max(width, height) // feather_base) | 1)))
        softened = cv2.GaussianBlur(mask, (feather_kernel, feather_kernel), 0)
        return (softened.astype(np.float32) / 255.0)[..., None]
