"""
Replicate SDXL Inpainting client cho virtual try-on.

Uses SDXL inpainting via Replicate API to create try-on images
with actual user image and garment image input.
"""

from replicate import Client
import base64
import io
import logging
import httpx
from PIL import Image
from typing import Optional

from src.config.settings import get_settings
from src.modules.image_generator.base import ImageGeneratorBase

logger = logging.getLogger(__name__)


class ReplicateGenerator(ImageGeneratorBase):
    """
    Replicate IDM-VTON Generator cho virtual try-on.

    Uses cuuupid/idm-vton with crop=True for faster processing.
    Proper visual try-on with user + garment image input.
    """

    # Try-on model selection
    # Option 1: IDM-VTON (proper visual try-on)
    MODEL_OWNER = "cuuupid"
    MODEL_NAME = "idm-vton"
    MODEL_VERSION = "0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985"

    # Option 2: Flux (text-to-image fallback)
    # MODEL_OWNER = "black-forest-labs"
    # MODEL_NAME = "flux-1.1-pro"
    # MODEL_VERSION = None

    def __init__(self):
        settings = get_settings()
        # Create authenticated client instance
        self.client = Client(
            api_token=settings.replicate_api_token,
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(settings.replicate_timeout),
                write=10.0,
                pool=10.0,
            ),
        )

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        """
        Generate try-on image sử dụng IDM-VTON.

        Args:
            base_image: Anonymized user image bytes
            garment_image: Product garment image bytes
            inpainting_prompt: Prompt từ Module 2 semantic parser (for category detection)
            mask: Mask image (not used by IDM-VTON)
            size: Output size (IDM-VTON outputs 768x1024)

        Returns:
            Generated image bytes
        """
        try:
            logger.info(f"Running {self.MODEL_NAME} via Replicate...")
            logger.info(f"Prompt preview: {inpainting_prompt[:100]}...")

            # Convert bytes to file-like objects
            human_img_io = io.BytesIO(base_image)
            human_img_io.name = "human.png"

            garm_img_io = io.BytesIO(garment_image)
            garm_img_io.name = "garment.png"

            # Log image info
            human_pil = Image.open(io.BytesIO(base_image))
            garment_pil = Image.open(io.BytesIO(garment_image))
            logger.info(
                f"Input sizes - Human: {human_pil.size}, Garment: {garment_pil.size}"
            )

            # Detect category from prompt
            prompt_lower = inpainting_prompt.lower()
            if any(kw in prompt_lower for kw in ["dress", "gown", "skirt"]):
                category = "dresses"
            elif any(
                kw in prompt_lower for kw in ["pants", "jeans", "trousers", "shorts"]
            ):
                category = "lower_body"
            else:
                category = "upper_body"

            # IDM-VTON inputs
            inputs = {
                "human_img": human_img_io,
                "garm_img": garm_img_io,
                "category": category,
                "crop": True,  # Enable crop for faster processing
                "seed": 42,
                "steps": 30,  # Standard quality steps
            }
            logger.info(f"IDM-VTON category: {category}, crop: True, steps: 30")

            # Create prediction (async)
            logger.info("Submitting to Replicate...")

            # Use model path for Flux, version for others
            if self.MODEL_VERSION:
                prediction = self.client.predictions.create(
                    version=self.MODEL_VERSION, input=inputs
                )
            else:
                prediction = self.client.predictions.create(
                    model=f"{self.MODEL_OWNER}/{self.MODEL_NAME}", input=inputs
                )

            logger.info(f"Prediction created: {prediction.id}")
            logger.info(f"Status: {prediction.status}")

            # Poll for result with timeout (IDM-VTON can take 2-4 minutes with crop)
            import time

            max_wait = 400  # 6.5 minutes max (more generous than before)
            start_time = time.time()
            poll_interval = 3  # Check every 3 seconds for faster feedback

            while prediction.status not in ["succeeded", "failed", "canceled"]:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        f"Prediction timeout after {elapsed:.0f}s. "
                        f"IDM-VTON may be slow/overloaded. Try again later."
                    )

                if elapsed % 15 < 3:  # Log every 15 seconds
                    logger.info(
                        f"Status: {prediction.status} (elapsed: {elapsed:.0f}s)"
                    )
                time.sleep(poll_interval)
                prediction.reload()

            if prediction.status != "succeeded":
                error_msg = getattr(prediction, "error", "Unknown error")
                raise ValueError(f"Prediction failed: {error_msg}")

            output = prediction.output
            if not output:
                raise ValueError("Replicate returned empty output")

            logger.info(f"Prediction succeeded! Output type: {type(output)}")

            # Handle output (list of URL strings from SDXL)
            if isinstance(output, list) and len(output) > 0:
                url = output[0]
                logger.info(f"Output URL: {url}")

                # Download image
                import httpx

                response = httpx.get(url, timeout=30.0)
                response.raise_for_status()
                image_bytes = response.content
                logger.info(f"Downloaded {len(image_bytes)} bytes")
            else:
                raise ValueError(f"Unexpected output format: {type(output)} - {output}")

            return image_bytes

            return image_bytes

        except Exception as e:
            logger.error(f"Replicate IDM-VTON failed: {str(e)}")
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
