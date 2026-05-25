"""
Direct product image URL ingestion.
"""

from dataclasses import dataclass
from urllib.parse import urlparse
import logging

import httpx

from src.config.settings import get_settings
from src.modules.privacy_guard.metadata_stripper import MetadataStripper

logger = logging.getLogger(__name__)


@dataclass
class ProductImageResult:
    source_url: str
    content_type: str
    image_base64: str
    normalized_format: str
    size_bytes: int


class ProductImageFetcher:
    """
    Fetch a direct image URL and normalize it for downstream try-on APIs.
    """

    def __init__(self):
        settings = get_settings()
        self.max_size_bytes = settings.max_upload_size_bytes
        self.timeout = min(float(settings.replicate_timeout), 30.0)

    @staticmethod
    def _validate_url(image_url: str) -> str:
        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http and https image URLs are supported")
        if not parsed.netloc:
            raise ValueError("Image URL must include a valid host")
        return image_url

    def _normalize_image_bytes(
        self,
        *,
        image_bytes: bytes,
        content_type: str,
        source_url: str,
    ) -> ProductImageResult:
        if not content_type.startswith("image/"):
            raise ValueError(
                f"Source did not contain an image. Content-Type was '{content_type or 'unknown'}'"
            )

        if not image_bytes:
            raise ValueError("Image source returned an empty response")
        if len(image_bytes) > self.max_size_bytes:
            raise ValueError(
                f"Image exceeds max size of {self.max_size_bytes // (1024 * 1024)} MB"
            )

        normalized_image = MetadataStripper.strip_metadata(image_bytes)
        normalized_bytes = normalized_image.getvalue()

        return ProductImageResult(
            source_url=source_url,
            content_type=content_type,
            image_base64=MetadataStripper.to_base64(normalized_bytes),
            normalized_format="jpeg",
            size_bytes=len(normalized_bytes),
        )

    async def normalize_uploaded_image(
        self,
        *,
        image_bytes: bytes,
        filename: str | None,
        content_type: str | None,
        source_label: str,
    ) -> ProductImageResult:
        """
        Normalize an uploaded garment image or screenshot for downstream try-on APIs.
        """
        effective_content_type = (content_type or "").split(";")[0].strip()
        source_url = f"{source_label}://{filename or 'uploaded-image'}"
        logger.info("Normalizing uploaded product image from %s", source_url)
        return self._normalize_image_bytes(
            image_bytes=image_bytes,
            content_type=effective_content_type,
            source_url=source_url,
        )

    async def fetch_image_from_url(self, image_url: str) -> ProductImageResult:
        """
        Download and normalize an image from a direct URL.
        """
        image_url = self._validate_url(image_url)
        logger.info(f"Fetching product image from URL: {image_url}")

        headers = {
            "User-Agent": "tryon-visual-project/0.1",
            "Accept": "image/*",
        }

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            headers=headers,
        ) as client:
            response = await client.get(image_url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        return self._normalize_image_bytes(
            image_bytes=response.content,
            content_type=content_type,
            source_url=image_url,
        )
