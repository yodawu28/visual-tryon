import base64
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src.api.routes.generation import _generate_tryon_payload


def _encode_color_image_b64(color_bgr: tuple[int, int, int], size: int = 32) -> str:
    image = np.full((size, size, 3), color_bgr, dtype=np.uint8)
    success, buffer = cv2.imencode(".png", image)
    assert success
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _encode_half_mask_b64(size: int = 32) -> str:
    mask = np.zeros((size, size), dtype=np.uint8)
    mask[:, : size // 2] = 255
    success, buffer = cv2.imencode(".png", mask)
    assert success
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _encode_leaky_face_mask_b64(size: int = 64) -> str:
    mask = np.zeros((size, size), dtype=np.uint8)
    mask[40:56, 24:40] = 255
    mask[12:28, 24:40] = 64
    success, buffer = cv2.imencode(".png", mask)
    assert success
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _decode_image_b64(image_b64: str) -> np.ndarray:
    decoded = base64.b64decode(image_b64)
    image = cv2.imdecode(np.frombuffer(decoded, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


class TestGenerationMasking:
    def test_qwen_fast_does_not_auto_composite_when_no_mask_is_provided(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        base_image_b64 = _encode_color_image_b64((0, 0, 255), size=64)
        generated_image_b64 = _encode_color_image_b64((255, 0, 0), size=64)
        product_image_b64 = _encode_color_image_b64((0, 255, 0), size=64)

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ), patch(
            "src.api.routes.generation.qwen_face_preserve_detector.detect_faces",
            return_value=[],
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=None,
                size="1024x1024",
            )

        assert payload["mask_supported"] is True
        assert payload["mask_applied"] is False
        assert payload["is_preview"] is True
        assert payload["replicate_model"] == "qwen/qwen-image-edit-2511"
        assert payload["model_warning"]

        composited = _decode_image_b64(payload["generated_image"])
        torso_pixel = composited[44, 32].tolist()
        side_pixel = composited[44, 8].tolist()
        corner_pixel = composited[4, 4].tolist()

        assert torso_pixel == [255, 0, 0]
        assert side_pixel == [255, 0, 0]
        assert corner_pixel == [255, 0, 0]

    def test_qwen_fast_preserves_anonymized_face_region_without_mask(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        base = np.full((64, 64, 3), (0, 0, 255), dtype=np.uint8)
        base[16:40, 20:44] = (0, 255, 255)
        generated = np.full((64, 64, 3), (255, 0, 0), dtype=np.uint8)

        success, base_buffer = cv2.imencode(".png", base)
        assert success
        success, generated_buffer = cv2.imencode(".png", generated)
        assert success

        base_image_b64 = base64.b64encode(base_buffer.tobytes()).decode("utf-8")
        generated_image_b64 = base64.b64encode(generated_buffer.tobytes()).decode(
            "utf-8"
        )
        product_image_b64 = _encode_color_image_b64((0, 255, 0), size=64)

        class FakeFace:
            bbox = np.array([20, 16, 44, 40], dtype=np.float32)

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ), patch(
            "src.api.routes.generation.qwen_face_preserve_detector.detect_faces",
            return_value=[FakeFace()],
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=None,
                size="1024x1024",
            )

        preserved = _decode_image_b64(payload["generated_image"])
        center_pixel = preserved[28, 32].tolist()
        corner_pixel = preserved[4, 4].tolist()

        assert center_pixel != [255, 0, 0]
        assert corner_pixel == [255, 0, 0]

    def test_qwen_fast_falls_back_to_generated_face_detection(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        base = np.full((64, 64, 3), (0, 0, 255), dtype=np.uint8)
        base[16:40, 20:44] = (0, 255, 255)
        generated = np.full((64, 64, 3), (255, 0, 0), dtype=np.uint8)

        success, base_buffer = cv2.imencode(".png", base)
        assert success
        success, generated_buffer = cv2.imencode(".png", generated)
        assert success

        base_image_b64 = base64.b64encode(base_buffer.tobytes()).decode("utf-8")
        generated_image_b64 = base64.b64encode(generated_buffer.tobytes()).decode(
            "utf-8"
        )
        product_image_b64 = _encode_color_image_b64((0, 255, 0), size=64)

        class FakeFace:
            bbox = np.array([20, 16, 44, 40], dtype=np.float32)

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ), patch(
            "src.api.routes.generation.qwen_face_preserve_detector.detect_faces",
            side_effect=[[], [FakeFace()]],
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=None,
                size="1024x1024",
            )

        preserved = _decode_image_b64(payload["generated_image"])
        center_pixel = preserved[28, 32].tolist()
        corner_pixel = preserved[4, 4].tolist()

        assert center_pixel != [255, 0, 0]
        assert corner_pixel == [255, 0, 0]

    def test_qwen_fast_preserves_original_face_bbox_when_detection_fails(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        base = np.full((64, 64, 3), (0, 0, 255), dtype=np.uint8)
        base[16:40, 20:44] = (0, 255, 255)
        generated = np.full((64, 64, 3), (255, 0, 0), dtype=np.uint8)

        success, base_buffer = cv2.imencode(".png", base)
        assert success
        success, generated_buffer = cv2.imencode(".png", generated)
        assert success

        base_image_b64 = base64.b64encode(base_buffer.tobytes()).decode("utf-8")
        generated_image_b64 = base64.b64encode(generated_buffer.tobytes()).decode(
            "utf-8"
        )
        product_image_b64 = _encode_color_image_b64((0, 255, 0), size=64)

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ), patch(
            "src.api.routes.generation.qwen_face_preserve_detector.detect_faces",
            return_value=[],
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=None,
                size="1024x1024",
                preserve_face_bboxes=[(20, 16, 44, 40)],
            )

        preserved = _decode_image_b64(payload["generated_image"])
        center_pixel = preserved[28, 32].tolist()

        assert center_pixel != [255, 0, 0]
        assert payload["face_preserve_applied"] is True
        assert payload["face_preserve_source"] == "full-flow original face bbox"

    def test_qwen_fast_applies_mask_composite(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        base_image_b64 = _encode_color_image_b64((0, 0, 255))
        generated_image_b64 = _encode_color_image_b64((255, 0, 0))
        product_image_b64 = _encode_color_image_b64((0, 255, 0))
        mask_b64 = _encode_half_mask_b64()

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=mask_b64,
                size="1024x1024",
            )

        assert payload["mask_supported"] is True
        assert payload["mask_applied"] is True

        composited = _decode_image_b64(payload["generated_image"])
        left_pixel = composited[8, 8].tolist()
        right_pixel = composited[8, 24].tolist()

        assert left_pixel == [255, 0, 0]
        assert right_pixel == [0, 0, 255]

    def test_qwen_fast_mask_composite_hard_locks_low_confidence_face_area(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        base_image_b64 = _encode_color_image_b64((0, 0, 255), size=64)
        generated_image_b64 = _encode_color_image_b64((255, 0, 0), size=64)
        product_image_b64 = _encode_color_image_b64((0, 255, 0), size=64)
        mask_b64 = _encode_leaky_face_mask_b64()

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ), patch(
            "src.api.routes.generation.qwen_face_preserve_detector.detect_faces",
            return_value=[],
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=mask_b64,
                size="1024x1024",
            )

        composited = _decode_image_b64(payload["generated_image"])
        face_pixel = composited[20, 32].tolist()
        torso_pixel = composited[48, 32].tolist()

        assert face_pixel == [0, 0, 255]
        assert torso_pixel == [255, 0, 0]

    def test_qwen_fast_rejects_invalid_mask_placeholder(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=_encode_color_image_b64((255, 0, 0)),
        ):
            try:
                _generate_tryon_payload(
                    anonymized_user_image=_encode_color_image_b64((0, 0, 255)),
                    product_image=_encode_color_image_b64((0, 255, 0)),
                    inpainting_prompt="Swap shirt",
                    mask="bnVsbA",
                    size="1024x1024",
                )
                assert False, "Expected ValueError for invalid mask payload"
            except ValueError as exc:
                assert "mask must be a supported image" in str(exc)

    def test_replicate_preview_mode_uses_same_preview_postprocessing(self):
        settings = Mock()
        settings.image_gen_mode = "replicate-preview"
        settings.replicate_preview_model = "example/new-preview-model"
        settings.replicate_preview_model_version = None
        settings.replicate_preview_model_warning = "Custom preview warning."

        base_image_b64 = _encode_color_image_b64((0, 0, 255), size=64)
        generated_image_b64 = _encode_color_image_b64((255, 0, 0), size=64)
        product_image_b64 = _encode_color_image_b64((0, 255, 0), size=64)

        with patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image_b64,
        ), patch(
            "src.api.routes.generation.qwen_face_preserve_detector.detect_faces",
            return_value=[],
        ):
            payload = _generate_tryon_payload(
                anonymized_user_image=base_image_b64,
                product_image=product_image_b64,
                inpainting_prompt="Swap shirt",
                mask=None,
                size="1024x1024",
            )

        assert payload["generator_mode"] == "replicate-preview"
        assert payload["is_preview"] is True
        assert payload["is_actual_tryon"] is False
        assert payload["replicate_model"] == "example/new-preview-model"
        assert payload["model_warning"] == "Custom preview warning."
