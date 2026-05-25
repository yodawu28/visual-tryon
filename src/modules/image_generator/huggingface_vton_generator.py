"""
HuggingFace Spaces IDM-VTON Generator cho virtual try-on.

Uses IDM-VTON hosted on HuggingFace Spaces via gradio_client.
Zero setup, uses their GPU, proper visual try-on.
"""

import base64
import logging
from typing import Optional
from gradio_client import Client, handle_file

from src.modules.image_generator.base import ImageGeneratorBase

logger = logging.getLogger(__name__)


class HuggingFaceVTONGenerator(ImageGeneratorBase):
    """
    HuggingFace Spaces IDM-VTON Generator.

    Uses yisol/IDM-VTON hosted demo for proper virtual try-on
    with user image + garment image input.
    """

    SPACE_ID = "yisol/IDM-VTON"

    def __init__(self):
        """Initialize generator (lazy client creation)."""
        self.client = None
        logger.info(
            "HuggingFace VTON generator created (client will init on first use)"
        )

    def _get_client(self):
        """Lazy initialize client on first use."""
        if self.client is None:
            try:
                logger.info(f"Initializing HF Spaces client: {self.SPACE_ID}")
                self.client = Client(self.SPACE_ID)
                logger.info("Client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize HF Spaces client: {e}")
                raise ValueError(
                    f"HuggingFace Space unavailable. Space may be down or restarting. Error: {str(e)}"
                )
        return self.client

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        """
        Generate try-on image using HuggingFace Spaces IDM-VTON.

        Args:
            base_image: Anonymized user image bytes
            garment_image: Product garment image bytes
            inpainting_prompt: Prompt from semantic parser (for category)
            mask: Not used by IDM-VTON
            size: Output size (IDM-VTON outputs 768x1024)

        Returns:
            Generated image bytes
        """
        try:
            logger.info("Running IDM-VTON via HuggingFace Spaces...")

            # Save images to temp files (gradio_client requires file paths)
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as user_tmp:
                user_tmp.write(base_image)
                user_path = user_tmp.name

            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False
            ) as garment_tmp:
                garment_tmp.write(garment_image)
                garment_path = garment_tmp.name

            # Detect category from prompt
            prompt_lower = inpainting_prompt.lower()
            if any(kw in prompt_lower for kw in ["dress", "gown", "skirt"]):
                category = "Dress"
            elif any(
                kw in prompt_lower for kw in ["pants", "jeans", "trousers", "shorts"]
            ):
                category = "Lower body"
            else:
                category = "Upper body"

            logger.info(f"Category: {category}")

            # Call HuggingFace Spaces API (lazy init client)
            # API signature: predict(dict, garm_img, garment_des, is_checked, is_checked_crop, denoise_steps, seed, fn_index=0)
            client = self._get_client()
            result = client.predict(
                {"background": handle_file(user_path), "layers": [], "composite": None},
                handle_file(garment_path),
                category,  # garment_des
                True,  # is_checked (auto-mask)
                False,  # is_checked_crop
                30,  # denoise_steps
                42,  # seed
                api_name="/tryon",
            )

            # Cleanup temp files
            os.unlink(user_path)
            os.unlink(garment_path)

            # Result is tuple: (output_image_path, masked_image_path)
            output_path = result[0]
            logger.info(f"IDM-VTON output: {output_path}")

            # Read output image
            with open(output_path, "rb") as f:
                image_bytes = f.read()

            logger.info(f"Downloaded {len(image_bytes)} bytes")

            return image_bytes

        except Exception as e:
            logger.error(f"HuggingFace Spaces IDM-VTON failed: {str(e)}")
            raise ValueError(f"Image generation failed: {str(e)}")

    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: Optional[str] = None,
        size: str = "1024x1024",
    ) -> str:
        """
        Generate try-on image from base64 inputs, return base64.
        """
        # Decode base64 to bytes
        base_image = base64.b64decode(base_image_b64)
        garment_image = base64.b64decode(garment_image_b64)
        mask = base64.b64decode(mask_b64) if mask_b64 else None

        # Generate
        result_bytes = self.generate_tryon(
            base_image=base_image,
            garment_image=garment_image,
            inpainting_prompt=inpainting_prompt,
            mask=mask,
            size=size,
        )

        # Encode back to base64
        return base64.b64encode(result_bytes).decode("utf-8")
