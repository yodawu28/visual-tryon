"""
EXIF metadata removal để bảo vệ privacy.
"""

from PIL import Image
import io
from typing import Union
import base64


class MetadataStripper:
    """
    Strip all EXIF/XMP metadata from images.
    """

    @staticmethod
    def strip_metadata(image: Union[Image.Image, bytes, io.BytesIO]) -> io.BytesIO:
        """
        Remove all metadata from image.

        Args:
            image: PIL Image hoặc bytes hoặc BytesIO

        Returns:
            BytesIO object chứa clean image (no metadata)
        """
        if isinstance(image, bytes):
            image = Image.open(io.BytesIO(image))
        elif isinstance(image, io.BytesIO):
            image = Image.open(image)

        # Create new image without metadata
        # Convert to RGB if necessary
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Save to BytesIO without EXIF
        output = io.BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=95,
            optimize=True,
            # CRITICAL: Don't pass exif parameter to remove metadata
        )
        output.seek(0)

        return output

    @staticmethod
    def to_base64(image_bytes: Union[bytes, io.BytesIO]) -> str:
        """
        Convert image to base64 string for API transmission.
        """
        if isinstance(image_bytes, io.BytesIO):
            image_bytes = image_bytes.getvalue()

        return base64.b64encode(image_bytes).decode("utf-8")
