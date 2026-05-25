"""
DALL-E 3 Image Generation client cho virtual try-on.

Uses DALL-E 3 generation mode (not inpainting) to create try-on images
from detailed prompts. Generates new images based on semantic analysis.
"""

from openai import OpenAI
import base64
import io
import logging
from PIL import Image
from typing import Optional

from src.config.settings import get_settings
from src.modules.image_generator.base import ImageGeneratorBase

logger = logging.getLogger(__name__)


class DALLEGenerator(ImageGeneratorBase):
    """
    DALL-E 3 Generator cho virtual try-on.

    Uses DALL-E 3 generation (not inpainting) to create full images
    from detailed semantic prompts.
    """

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        """
        Generate try-on image sử dụng DALL-E 3 generation.

        Note: DALL-E 3 không support inpainting. Generate full new image
        từ detailed prompt enhanced with garment color/pattern analysis.

        DALL-E 3 sizes: 1024x1024, 1024x1792, 1792x1024
        """
        # Analyze garment for color/pattern details
        garment_details = self._analyze_garment(garment_image)

        # Build enhanced prompt with garment analysis
        enhanced_prompt = self._build_enhanced_prompt(
            inpainting_prompt, garment_details
        )

        # Validate size for DALL-E 3
        valid_sizes = ["1024x1024", "1024x1792", "1792x1024"]
        if size not in valid_sizes:
            logger.warning(f"Size {size} not valid for DALL-E 3, using 1024x1024")
            size = "1024x1024"

        # Call DALL-E 3 Generation API
        try:
            logger.info("Calling DALL-E 3 Generation API...")
            logger.info(f"Enhanced prompt: {enhanced_prompt[:200]}...")

            # Try DALL-E 3, fallback to DALL-E 2
            try:
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=enhanced_prompt[:4000],  # DALL-E 3 max 4000 chars
                    size=size,
                    quality="standard",  # "standard" or "hd"
                    n=1,
                )
            except Exception as e:
                if "does not exist" in str(e):
                    logger.warning(
                        "DALL-E 3 not available, falling back to DALL-E 2..."
                    )
                    # DALL-E 2 only supports 256x256, 512x512, 1024x1024
                    dalle2_size = "1024x1024"
                    response = self.client.images.generate(
                        model="dall-e-2",
                        prompt=enhanced_prompt[:1000],  # DALL-E 2 max 1000 chars
                        size=dalle2_size,
                        n=1,
                    )
                else:
                    raise

            # Download generated image
            image_url = response.data[0].url
            logger.info(f"Generated image URL: {image_url}")

            # Fetch image from URL
            import httpx

            with httpx.Client() as client:
                img_response = client.get(image_url)
                img_response.raise_for_status()
                return img_response.content

        except Exception as e:
            logger.error(f"DALL-E 3 Generation API failed: {str(e)}")
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
        Generate try-on image từ base64 inputs, return base64.
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

    def _analyze_garment(self, garment_image: bytes) -> dict:
        """
        Analyze garment image để extract màu, pattern details.

        Args:
            garment_image: Garment image bytes

        Returns:
            Dict với dominant_colors, brightness, patterns
        """
        try:
            img = Image.open(io.BytesIO(garment_image))
            img = img.convert("RGB")

            # Resize for faster processing
            img.thumbnail((200, 200))

            # Get dominant colors (top 3)
            pixels = list(img.getdata())
            from collections import Counter

            color_counts = Counter(pixels)
            top_colors = color_counts.most_common(3)

            # Convert RGB to color names (simple mapping)
            def rgb_to_name(rgb):
                r, g, b = rgb
                if r > 200 and g > 200 and b > 200:
                    return "white"
                elif r < 50 and g < 50 and b < 50:
                    return "black"
                elif r > g and r > b:
                    return "red" if r > 150 else "brown"
                elif g > r and g > b:
                    return "green"
                elif b > r and b > g:
                    return "blue" if b > 150 else "navy"
                elif r > 150 and g > 150:
                    return "yellow"
                elif r > 100 and g < 100 and b > 100:
                    return "purple"
                else:
                    return "gray"

            color_names = [rgb_to_name(color[0]) for color in top_colors]

            # Calculate brightness
            brightness = sum(pixels[0]) / 3 if pixels else 128

            logger.info(
                f"Garment analysis - Colors: {color_names}, Brightness: {brightness:.0f}"
            )

            return {
                "dominant_colors": color_names,
                "brightness": "bright" if brightness > 180 else "dark",
            }

        except Exception as e:
            logger.warning(f"Garment analysis failed: {e}")
            return {"dominant_colors": ["unknown"], "brightness": "neutral"}

    def _build_enhanced_prompt(
        self, inpainting_prompt: str, garment_details: dict
    ) -> str:
        """
        Build enhanced prompt for DALL-E 3 generation with garment details.

        Args:
            inpainting_prompt: Prompt từ Module 2 semantic parser
            garment_details: Dict từ _analyze_garment()

        Returns:
            Enhanced detailed prompt for DALL-E 3
        """
        # Extract color info
        colors = garment_details.get("dominant_colors", [])
        brightness = garment_details.get("brightness", "neutral")

        color_desc = ", ".join(colors[:2]) if colors else "colored"

        # Add quality modifiers with color details
        quality_prefix = "High quality photorealistic photo, "
        color_injection = f"with {color_desc} {brightness} tones, "
        quality_suffix = ", detailed fabric texture, natural studio lighting, professional photography"

        # Combine
        enhanced = (
            f"{quality_prefix}{inpainting_prompt} {color_injection}{quality_suffix}"
        )

        # Ensure reasonable length (DALL-E 3 max 4000 chars)
        if len(enhanced) > 4000:
            enhanced = enhanced[:3997] + "..."

        logger.info(f"Enhanced prompt: {enhanced[:150]}...")

        return enhanced
