import base64

import cv2
import numpy as np

from src.modules.evaluation.output_safety import PreviewOutputSafetyPostprocessor


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


def _decode_image_b64(image_b64: str) -> np.ndarray:
    decoded = base64.b64decode(image_b64)
    image = cv2.imdecode(np.frombuffer(decoded, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def test_preview_output_safety_does_not_apply_mask_by_default():
    detector = _Detector([])
    postprocessor = PreviewOutputSafetyPostprocessor(face_detector=detector)

    result = postprocessor(
        base_image_b64=_encode_color_image_b64((0, 0, 255)),
        generated_image_b64=_encode_color_image_b64((255, 0, 0)),
        mask_b64=_encode_half_mask_b64(),
        preview_metadata={"input_mapping": "multi_image_edit"},
    )

    composited = _decode_image_b64(result.image_b64)
    assert composited[8, 8].tolist() == [255, 0, 0]
    assert composited[8, 24].tolist() == [255, 0, 0]
    assert result.mask_applied is False
    assert result.mask_source is None
    assert result.face_preserve_applied is False


def test_preview_output_safety_composites_masked_qwen_output_when_enabled():
    detector = _Detector([])
    postprocessor = PreviewOutputSafetyPostprocessor(
        face_detector=detector,
        apply_mask=True,
    )

    result = postprocessor(
        base_image_b64=_encode_color_image_b64((0, 0, 255)),
        generated_image_b64=_encode_color_image_b64((255, 0, 0)),
        mask_b64=_encode_half_mask_b64(),
        preview_metadata={"input_mapping": "multi_image_edit"},
    )

    composited = _decode_image_b64(result.image_b64)
    assert composited[8, 8].tolist() == [255, 0, 0]
    assert composited[8, 24].tolist() == [0, 0, 255]
    assert result.mask_applied is True
    assert result.mask_source == "manifest"
    assert result.face_preserve_applied is False


def test_preview_output_safety_restores_anonymized_face_region_for_qwen():
    base = np.full((64, 64, 3), (0, 0, 255), dtype=np.uint8)
    base[16:40, 20:44] = (0, 255, 255)
    generated = np.full((64, 64, 3), (255, 0, 0), dtype=np.uint8)
    detector = _Detector([_Face([20, 16, 44, 40])])
    postprocessor = PreviewOutputSafetyPostprocessor(face_detector=detector)

    result = postprocessor(
        base_image_b64=_encode_image_b64(base),
        generated_image_b64=_encode_image_b64(generated),
        mask_b64=None,
        preview_metadata={"input_mapping": "multi_image_edit"},
    )

    composited = _decode_image_b64(result.image_b64)
    assert composited[28, 32].tolist() != [255, 0, 0]
    assert composited[4, 4].tolist() == [255, 0, 0]
    assert result.mask_applied is False
    assert result.face_preserve_applied is True
    assert result.face_preserve_source == "anonymized base image"


def test_preview_output_safety_skips_non_qwen_mapping():
    detector = _Detector([_Face([20, 16, 44, 40])])
    postprocessor = PreviewOutputSafetyPostprocessor(face_detector=detector)
    generated_image_b64 = _encode_color_image_b64((255, 0, 0), size=64)

    result = postprocessor(
        base_image_b64=_encode_color_image_b64((0, 0, 255), size=64),
        generated_image_b64=generated_image_b64,
        mask_b64=_encode_half_mask_b64(size=64),
        preview_metadata={"input_mapping": "google_nano_banana"},
    )

    assert result.image_b64 == generated_image_b64
    assert result.mask_applied is False
    assert result.face_preserve_applied is False
    assert detector.calls == 0


def _encode_image_b64(image: np.ndarray) -> str:
    success, buffer = cv2.imencode(".png", image)
    assert success
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


class _Face:
    def __init__(self, bbox: list[int]):
        self.bbox = np.array(bbox, dtype=np.float32)


class _Detector:
    def __init__(self, faces: list[_Face]):
        self.faces = faces
        self.calls = 0

    def detect_faces(self, image):
        self.calls += 1
        return self.faces
