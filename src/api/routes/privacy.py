"""
Privacy Guard API endpoints.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import cv2
import io
import numpy as np
import logging

from src.modules.privacy_guard.face_detector import FaceDetector
from src.modules.privacy_guard.face_anonymizer import FaceAnonymizer
from src.modules.privacy_guard.metadata_stripper import MetadataStripper
from src.schemas.responses import PrivacyGuardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])

# Singleton instances
face_detector = FaceDetector()
face_anonymizer = FaceAnonymizer()
metadata_stripper = MetadataStripper()


def anonymize_image_bytes(
    *,
    image_bytes: bytes,
    privacy_level: str,
) -> tuple[str, int, bytes]:
    """
    Shared anonymization helper used by both the privacy endpoint and full-flow try-on.
    Returns base64-encoded anonymized JPEG plus detected face count.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(400, "Invalid image file")

    if privacy_level not in {"standard", "strong", "extreme"}:
        raise HTTPException(
            400, "Invalid privacy_level. Supported: standard, strong, extreme"
        )

    faces = face_detector.detect_faces(image)
    if not faces:
        raise HTTPException(404, "No faces detected in image")

    logger.info(f"Detected {len(faces)} face(s) in image")

    anonymized = face_anonymizer.anonymize(
        image,
        faces,
        privacy_level=privacy_level,
    )

    success, buffer = cv2.imencode(".jpg", anonymized)
    if not success:
        raise HTTPException(500, "Failed to encode anonymized image")

    clean_image = metadata_stripper.strip_metadata(buffer.tobytes())
    clean_image_bytes = clean_image.getvalue()
    base64_str = metadata_stripper.to_base64(clean_image_bytes)
    return base64_str, len(faces), clean_image_bytes


@router.post("/anonymize", response_model=PrivacyGuardResponse)
async def anonymize_image(
    file: UploadFile = File(..., description="Image file to anonymize"),
    return_format: str = "base64",  # "base64" or "stream"
    privacy_level: str = "standard",  # "standard" | "strong" | "extreme"
):
    """
    Anonymize faces trong uploaded image.

    Process:
    1. Detect faces
    2. Swap faces với neutral AI face (or fallback to blur)
    3. Strip EXIF metadata
    4. Return as base64 hoặc stream

    **Privacy Guarantee**: Tất cả xử lý diễn ra LOCAL, không có network call.
    """
    try:
        # Read uploaded file
        contents = await file.read()
        base64_str, face_count, clean_image_bytes = anonymize_image_bytes(
            image_bytes=contents,
            privacy_level=privacy_level,
        )

        # Step 4: Format response
        if return_format == "base64":
            return PrivacyGuardResponse(
                success=True,
                faces_detected=face_count,
                anonymized_image=base64_str,
                format="base64",
                message=(
                    "Image anonymized successfully. All metadata removed. "
                    f"Privacy level: {privacy_level}."
                ),
            )
        else:
            # For stream, return as response
            return StreamingResponse(
                io.BytesIO(clean_image_bytes),
                media_type="image/jpeg",
                headers={
                    "X-Faces-Detected": str(face_count),
                    "X-Privacy-Processed": "true",
                    "X-Privacy-Level": privacy_level,
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anonymization failed: {str(e)}")
        raise HTTPException(500, f"Anonymization failed: {str(e)}")
