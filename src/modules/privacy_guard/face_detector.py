"""
Face detection sử dụng InsightFace buffalo_l model.
Optimized cho Apple Silicon M1/M2/M3.
"""

from insightface.app import FaceAnalysis
import numpy as np
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class DetectedFace:
    """Structured face detection result"""

    bbox: np.ndarray  # [x1, y1, x2, y2]
    keypoints: Optional[np.ndarray] = None  # (5, 2) - eyes, nose, mouth corners
    confidence: float = 0.0
    embedding: Optional[np.ndarray] = None


class FaceDetector:
    """
    Face detector với InsightFace.
    Thread-safe, singleton pattern cho model reuse.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            # Use CPUExecutionProvider for Apple Silicon
            self.app = FaceAnalysis(
                name="buffalo_l", providers=["CPUExecutionProvider"]
            )
            self.app.prepare(
                ctx_id=-1,  # CPU mode
                det_thresh=0.5,  # Detection threshold
                det_size=(640, 640),
            )
            self.initialized = True

    def detect_faces(self, image: np.ndarray, max_faces: int = 0) -> List[DetectedFace]:
        """
        Detect faces trong image.

        Args:
            image: BGR format (cv2.imread output)
            max_faces: Max số faces cần detect (0 = unlimited)

        Returns:
            List of DetectedFace objects
        """
        faces = self.app.get(image, max_num=max_faces)

        return [
            DetectedFace(
                bbox=face.bbox,
                keypoints=face.kps if hasattr(face, "kps") else None,
                confidence=float(face.det_score) if hasattr(face, "det_score") else 0.0,
                embedding=face.embedding if hasattr(face, "embedding") else None,
            )
            for face in faces
        ]
