"""
Base class cho image generation backends.
"""

from abc import ABC, abstractmethod
from typing import Optional


class ImageGeneratorBase(ABC):
    """
    Abstract base class cho different image generation providers.
    Cho phép switch giữa DALL-E 3, Imagen 3, etc.
    """

    @abstractmethod
    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        """
        Generate try-on image using garment reference.

        Args:
            base_image: Anonymized user image (bytes)
            garment_image: Product garment image for visual reference (bytes)
            inpainting_prompt: Optimized prompt từ Module 2
            mask: Optional mask image (white = edit area, black = keep)
            size: Output image size

        Returns:
            Generated image bytes

        Note: Garment image usage depends on generator:
        - IDM-VTON: Uses garment as visual reference
        - DALL-E: Analyzes colors/patterns, injects into prompt
        - SDXL: Currently ignores garment (text prompt only)
        """
        pass

    @abstractmethod
    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: Optional[str] = None,
        size: str = "1024x1024",
    ) -> str:
        """
        Generate try-on image từ base64 inputs.

        Args:
            base_image_b64: Base64 encoded anonymized image
            garment_image_b64: Base64 encoded garment image
            inpainting_prompt: Optimized prompt từ Module 2
            mask_b64: Optional base64 encoded mask
            size: Output image size

        Returns:
            Generated image as base64 string
        """
        pass
