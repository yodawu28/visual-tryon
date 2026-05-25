"""
Tests cho Privacy Guard module.
"""

import pytest
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.privacy import router as privacy_router
from src.modules.privacy_guard.face_detector import FaceDetector, DetectedFace
from src.modules.privacy_guard.face_anonymizer import FaceAnonymizer
from src.modules.privacy_guard.metadata_stripper import MetadataStripper


@pytest.fixture
def sample_image():
    """Create sample image for testing"""
    # Generate 640x480 test image
    img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return img


@pytest.fixture
def face_detector():
    return FaceDetector()


@pytest.fixture
def face_anonymizer():
    return FaceAnonymizer()


@pytest.fixture
def metadata_stripper():
    return MetadataStripper()


class TestFaceDetector:
    def test_singleton_pattern(self):
        """Verify FaceDetector is singleton"""
        detector1 = FaceDetector()
        detector2 = FaceDetector()
        assert detector1 is detector2

    def test_detect_faces_no_faces(self, face_detector, sample_image):
        """Test detection on image without faces"""
        faces = face_detector.detect_faces(sample_image)
        # Random noise không có faces
        assert isinstance(faces, list)

    def test_detect_faces_returns_correct_type(self, face_detector, sample_image):
        """Verify return type is list of DetectedFace"""
        faces = face_detector.detect_faces(sample_image)
        assert all(isinstance(face, DetectedFace) for face in faces)


class TestFaceAnonymizer:
    def test_anonymize_empty_faces_list(self, face_anonymizer, sample_image):
        """Test anonymization với empty faces list"""
        result = face_anonymizer.anonymize(sample_image, [])
        assert result.shape == sample_image.shape
        # Should return a copy with identical content
        assert result is not sample_image
        assert np.array_equal(result, sample_image)

    def test_fallback_anonymization(self, face_anonymizer, sample_image):
        """Test fallback anonymization changes the face region"""

        # Create fake face with bbox
        class FakeFace:
            def __init__(self):
                self.bbox = np.array([100, 100, 200, 200])

        faces = [FakeFace()]
        result = face_anonymizer._fallback_anonymize(sample_image.copy(), faces)

        assert result.shape == sample_image.shape
        # Region should be different (blurred/pixelated)
        region_original = sample_image[100:200, 100:200]
        region_anonymized = result[100:200, 100:200]
        assert not np.array_equal(region_original, region_anonymized)

    def test_fallback_anonymization_expands_beyond_face_bbox(
        self, face_anonymizer, sample_image
    ):
        """Fallback should also anonymize context around the face bbox."""

        class FakeFace:
            def __init__(self):
                self.bbox = np.array([100, 100, 200, 200])

        faces = [FakeFace()]
        result = face_anonymizer._fallback_anonymize(sample_image.copy(), faces)

        # Expanded region should include pixels above and beside the original face box.
        expanded_original = sample_image[50:235, 65:235]
        expanded_anonymized = result[50:235, 65:235]
        assert not np.array_equal(expanded_original, expanded_anonymized)

    def test_expand_face_bbox_strong_is_larger_than_standard(self, face_anonymizer):
        standard = face_anonymizer._expand_face_bbox(
            100, 100, 200, 200, 640, 480, privacy_level="standard"
        )
        strong = face_anonymizer._expand_face_bbox(
            100, 100, 200, 200, 640, 480, privacy_level="strong"
        )
        extreme = face_anonymizer._expand_face_bbox(
            100, 100, 200, 200, 640, 480, privacy_level="extreme"
        )

        standard_area = (standard[2] - standard[0]) * (standard[3] - standard[1])
        strong_area = (strong[2] - strong[0]) * (strong[3] - strong[1])
        extreme_area = (extreme[2] - extreme[0]) * (extreme[3] - extreme[1])
        assert strong_area > standard_area
        assert extreme_area > strong_area

    def test_soft_face_mask_strong_covers_more_area(self, face_anonymizer):
        standard_mask = face_anonymizer._create_soft_face_mask(
            180, 220, privacy_level="standard"
        )
        strong_mask = face_anonymizer._create_soft_face_mask(
            180, 220, privacy_level="strong"
        )
        extreme_mask = face_anonymizer._create_soft_face_mask(
            180, 220, privacy_level="extreme"
        )

        assert float(strong_mask.sum()) > float(standard_mask.sum())
        assert float(extreme_mask.sum()) > float(strong_mask.sum())

    def test_low_detail_patch_strong_reduces_texture_more(self, face_anonymizer):
        region = np.random.randint(0, 255, (180, 160, 3), dtype=np.uint8)

        standard_patch = face_anonymizer._create_low_detail_patch(
            region, privacy_level="standard"
        )
        strong_patch = face_anonymizer._create_low_detail_patch(
            region, privacy_level="strong"
        )
        extreme_patch = face_anonymizer._create_low_detail_patch(
            region, privacy_level="extreme"
        )

        standard_var = float(np.var(standard_patch.astype(np.float32)))
        strong_var = float(np.var(strong_patch.astype(np.float32)))
        extreme_var = float(np.var(extreme_patch.astype(np.float32)))
        assert strong_var < standard_var
        assert extreme_var < strong_var


class TestMetadataStripper:
    def test_strip_metadata_from_bytes(self, metadata_stripper):
        """Test stripping metadata from bytes"""
        # Create simple image với metadata
        img = Image.new("RGB", (100, 100), color="red")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", exif=b"fake_exif_data")
        buffer.seek(0)

        # Strip metadata
        clean = metadata_stripper.strip_metadata(buffer.getvalue())

        assert isinstance(clean, BytesIO)
        # Verify it's valid image
        clean_img = Image.open(clean)
        assert clean_img.size == (100, 100)

    def test_to_base64(self, metadata_stripper):
        """Test base64 encoding"""
        test_bytes = b"test data"
        b64 = metadata_stripper.to_base64(test_bytes)

        assert isinstance(b64, str)
        assert len(b64) > 0

        # Verify it can be decoded
        import base64

        decoded = base64.b64decode(b64)
        assert decoded == test_bytes

    def test_strip_metadata_converts_rgba_to_rgb(self, metadata_stripper):
        """Test RGBA images are converted to RGB"""
        # Create RGBA image
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))

        clean = metadata_stripper.strip_metadata(img)
        clean_img = Image.open(clean)

        # Should be RGB, not RGBA
        assert clean_img.mode == "RGB"


class TestPrivacyRoute:
    def setup_method(self):
        app = FastAPI()
        app.include_router(privacy_router)
        self.client = TestClient(app)

    def test_anonymize_route_passes_privacy_level(self):
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".jpg", image)
        assert success

        class FakeFace:
            bbox = np.array([10, 10, 40, 40])

        with patch(
            "src.api.routes.privacy.face_detector.detect_faces",
            return_value=[FakeFace()],
        ), patch(
            "src.api.routes.privacy.face_anonymizer.anonymize",
            return_value=image,
        ) as anonymize_mock:
            response = self.client.post(
                "/api/v1/privacy/anonymize?privacy_level=strong",
                files={"file": ("face.jpg", encoded.tobytes(), "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert "Privacy level: strong" in payload["message"]
        anonymize_mock.assert_called_once()
        assert anonymize_mock.call_args.kwargs["privacy_level"] == "strong"

    def test_anonymize_route_accepts_extreme_privacy_level(self):
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".jpg", image)
        assert success

        class FakeFace:
            bbox = np.array([10, 10, 40, 40])

        with patch(
            "src.api.routes.privacy.face_detector.detect_faces",
            return_value=[FakeFace()],
        ), patch(
            "src.api.routes.privacy.face_anonymizer.anonymize",
            return_value=image,
        ) as anonymize_mock:
            response = self.client.post(
                "/api/v1/privacy/anonymize?privacy_level=extreme",
                files={"file": ("face.jpg", encoded.tobytes(), "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert "Privacy level: extreme" in payload["message"]
        assert anonymize_mock.call_args.kwargs["privacy_level"] == "extreme"

    def test_anonymize_route_rejects_invalid_privacy_level(self):
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".jpg", image)
        assert success

        response = self.client.post(
            "/api/v1/privacy/anonymize?privacy_level=maximum",
            files={"file": ("face.jpg", encoded.tobytes(), "image/jpeg")},
        )

        assert response.status_code == 400
        assert "Invalid privacy_level" in response.text
