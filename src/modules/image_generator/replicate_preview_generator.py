"""
Generic Replicate preview generator for virtual try-on.

This adapter targets multi-image edit models. The first image is the
anonymized user photo and the second image is the garment reference.
"""

import base64
import io
import logging
import re
from typing import Optional

import httpx
from replicate import Client

from src.config.settings import get_settings
from src.modules.image_generator.base import ImageGeneratorBase

logger = logging.getLogger(__name__)


class ReplicatePreviewGenerator(ImageGeneratorBase):
    """
    Fast preview generator backed by configurable Replicate image-edit models.

    This path is intended for quick iteration only. It uses both the anonymized
    user image and garment image as references, but the result is still a
    guided edit rather than a dedicated VTON output.
    """

    DEFAULT_MODEL = "qwen/qwen-image-edit-2511"
    DEFAULT_MODEL_WARNING = (
        "Replicate preview uses both the anonymized user image and garment image "
        "as references, but this is still a preview edit and may drift from the "
        "exact input person or garment."
    )
    DEFAULT_PREVIEW_PROMPT_VERSION = "preview-garment-swap-v1"
    PREVIEW_PROMPT_VARIANTS = {
        "preview-garment-swap-v1",
        "preview-garment-preserve-v2",
        "preview-qwen-controlled-v3",
        "preview-nano-full-replace-v3",
    }

    def __init__(self):
        settings = get_settings()
        self.model = settings.replicate_preview_model
        self.model_version = settings.replicate_preview_model_version
        self.input_mapping = settings.replicate_preview_input_mapping
        self.prompt_variant = self.DEFAULT_PREVIEW_PROMPT_VERSION
        self.go_fast = settings.replicate_preview_go_fast
        self.model_warning = (
            settings.replicate_preview_model_warning or self.DEFAULT_MODEL_WARNING
        )
        self.client = Client(
            api_token=settings.replicate_api_token,
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(settings.replicate_timeout),
                write=10.0,
                pool=10.0,
            ),
        )

    @staticmethod
    def _detect_target_region(inpainting_prompt: str) -> str:
        """Infer the clothing region to edit from the semantic prompt."""
        prompt_lower = inpainting_prompt.lower()

        if any(
            kw in prompt_lower
            for kw in ["dress", "gown", "full outfit", "one-piece", "one piece"]
        ):
            return "full outfit"
        if any(
            kw in prompt_lower
            for kw in ["pants", "jeans", "trousers", "shorts", "skirt", "lower body"]
        ):
            return "lower body clothing"
        if any(
            kw in prompt_lower
            for kw in [
                "shirt",
                "t-shirt",
                "tee",
                "jersey",
                "hoodie",
                "sweater",
                "cardigan",
                "jacket",
                "coat",
                "blouse",
                "top",
                "upper body",
            ]
        ):
            return "upper body clothing"
        return "upper body clothing"

    def get_preview_prompt_version(self) -> str:
        prompt_variant = getattr(
            self,
            "prompt_variant",
            self.DEFAULT_PREVIEW_PROMPT_VERSION,
        )
        if prompt_variant not in self.PREVIEW_PROMPT_VARIANTS:
            raise ValueError(f"Unsupported preview prompt variant: {prompt_variant}")
        return prompt_variant

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "preview_model": self.get_model_identifier(),
            "preview_input_mapping": self.input_mapping,
            "preview_prompt_version": self.get_preview_prompt_version(),
        }

    @classmethod
    def _build_preview_prompt_v1(cls, inpainting_prompt: str) -> str:
        """Build the original strict edit-only prompt for preview generation."""
        target_region = cls._detect_target_region(inpainting_prompt)
        return (
            "Edit only the first image. "
            "Use the second image only as a garment reference. "
            "Keep the first image as the base photo with the same anonymized person, "
            "same body shape, same pose, same hands and arms, same background, "
            "same camera angle, same crop, and the same anonymized face area. "
            "Keep the original camera texture, compression, blur, shadows, and color tone. "
            f"Change only the {target_region} in the first image. "
            "Put the garment from the second image onto the person in the first image. "
            "Preserve the garment type, colors, silhouette, collar, sleeve length, "
            "fabric appearance, logos, stripes, and visible design details from the second image. "
            "Do not beautify skin, sharpen the face, smooth the photo, or make the image look synthetic. "
            "Do not create a new person. "
            "Do not change the pose. "
            "Do not change the background. "
            "Do not restyle the image. "
            "Do not change the lighting style. "
            "If uncertain, keep the first image unchanged except for the clothing swap."
        )

    @classmethod
    def _build_preview_prompt_v2(cls, inpainting_prompt: str) -> str:
        """Build a stronger garment-preservation prompt for eval-only comparison."""
        target_region = cls._detect_target_region(inpainting_prompt)
        return (
            "Edit only the first image. "
            "Use the second image only as the garment reference. "
            "Keep the first image as the base photo with the same anonymized person, "
            "same body shape, same pose, same hands and arms, same camera framing, "
            "same background, same lighting, same crop, and same anonymized face area. "
            f"Change only the {target_region} in the first image. "
            "Transfer the garment from the second image onto the person in the first image. "
            "Preserve the exact garment color palette, silhouette, neckline or collar, "
            "sleeve shape and length, hem shape, fabric texture, fabric weight, folds, "
            "logos, patches, text, stripes, panels, seams, trims, and visible design details. "
            "Do not invent a different garment. "
            "Do not simplify or remove visible garment details. "
            "Keep the original camera texture, compression, blur, shadows, and color tone. "
            "Do not beautify skin, sharpen the face, smooth the photo, or make the image look synthetic. "
            "Do not create a new person, change the pose, change the background, "
            "restyle the image, or change the lighting style. "
            "If uncertain, keep the first image unchanged except for the clothing swap."
        )

    @classmethod
    def _build_preview_prompt_qwen_v3(cls, inpainting_prompt: str) -> str:
        """Build a controlled Qwen prompt to reduce redraws and hallucinated details."""
        target_region = cls._detect_target_region(inpainting_prompt)
        return (
            "Edit only the first image. "
            "Use the second image only as the exact garment reference. "
            "Keep the first image as the base photo with the same anonymized person, "
            "same body shape, same pose, same hands and arms, same background, "
            "same camera angle, same crop, same lighting, and same anonymized face area. "
            f"Change only the {target_region} in the first image. "
            "Replace the current garment with the garment from the second image. "
            "Preserve only the garment details that are visible in the second image: "
            "color palette, silhouette, neckline or collar, sleeve length, logos, text, "
            "stripes, panels, trims, seams, and fabric texture. "
            "Do not add any logos, text, graphics, stripes, or patterns that are not "
            "visible in the second image. "
            "Do not invent decorative details. "
            "Keep hands, arms, fingers, skin, and body outline unchanged. "
            "Do not redraw or reshape hands, arms, shoulders, neck, face, hair, or body. "
            "Keep the original camera texture, compression, blur, shadows, and color tone. "
            "If a garment detail is unclear, keep that area simple rather than inventing it."
        )

    @classmethod
    def _build_preview_prompt_nano_v3(cls, inpainting_prompt: str) -> str:
        """Build a Nano prompt that prioritizes full replacement of the old garment."""
        target_region = cls._detect_target_region(inpainting_prompt)
        return (
            "Edit only the first image. "
            "Use the second image only as the garment reference. "
            "Keep the first image as the base photo with the same anonymized person, "
            "same body shape, same pose, same hands and arms, same background, "
            "same camera framing, same lighting, same crop, and same anonymized face area. "
            f"Change only the {target_region} in the first image. "
            "Remove the entire existing upper garment from the first image, including "
            "the old collar, neckline, sleeves, cuffs, hem, fabric, color, and wrinkles. "
            "Replace it fully with the garment from the second image. "
            "If the reference garment is short-sleeve, do not keep the old long sleeves. "
            "If the reference garment has a different collar, hem, or silhouette, use the "
            "reference garment shape and do not preserve the old garment shape. "
            "The final clothing must look like the second image garment being worn by "
            "the person in the first image. "
            "Preserve the garment color, logos, text, stripes, trims, panels, and visible "
            "design details from the second image. "
            "Do not keep any visible part of the original garment unless it also appears "
            "in the second image. "
            "Do not change the face, hands, arms, pose, body shape, background, camera "
            "angle, or lighting."
        )

    @classmethod
    def _build_preview_prompt(cls, inpainting_prompt: str) -> str:
        return cls._build_preview_prompt_v1(inpainting_prompt)

    def _build_configured_preview_prompt(self, inpainting_prompt: str) -> str:
        prompt_variant = self.get_preview_prompt_version()
        if prompt_variant == "preview-garment-swap-v1":
            return self._build_preview_prompt_v1(inpainting_prompt)
        if prompt_variant == "preview-garment-preserve-v2":
            return self._build_preview_prompt_v2(inpainting_prompt)
        if prompt_variant == "preview-qwen-controlled-v3":
            return self._build_preview_prompt_qwen_v3(inpainting_prompt)
        if prompt_variant == "preview-nano-full-replace-v3":
            return self._build_preview_prompt_nano_v3(inpainting_prompt)
        raise ValueError(f"Unsupported preview prompt variant: {prompt_variant}")

    @staticmethod
    def _decode_base64_image(image_b64: str) -> bytes:
        if not image_b64:
            raise ValueError("Image payload is empty")

        normalized = image_b64.strip()
        if normalized.startswith("data:"):
            try:
                normalized = normalized.split("base64,", 1)[1]
            except IndexError as exc:
                raise ValueError("Invalid data URL image payload") from exc

        normalized = re.sub(r"\s+", "", normalized)
        normalized = normalized.replace("-", "+").replace("_", "/")

        missing_padding = len(normalized) % 4
        if missing_padding:
            normalized += "=" * (4 - missing_padding)

        try:
            return base64.b64decode(normalized, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 image payload") from exc

    @staticmethod
    def _named_image_io(image_bytes: bytes, filename: str) -> io.BytesIO:
        image_io = io.BytesIO(image_bytes)
        image_io.name = filename
        return image_io

    def _build_qwen_multi_image_inputs(
        self,
        *,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
    ) -> dict:
        return {
            "image": [
                self._named_image_io(base_image, "user.png"),
                self._named_image_io(garment_image, "garment.png"),
            ],
            "prompt": self._build_configured_preview_prompt(inpainting_prompt),
            "aspect_ratio": "match_input_image",
            "go_fast": self.go_fast,
            "seed": 42,
            "output_format": "png",
            "output_quality": 95,
        }

    def _build_google_nano_banana_inputs(
        self,
        *,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
    ) -> dict:
        return {
            "image_input": [
                self._named_image_io(base_image, "user.png"),
                self._named_image_io(garment_image, "garment.png"),
            ],
            "prompt": self._build_configured_preview_prompt(inpainting_prompt),
            "aspect_ratio": "match_input_image",
            "output_format": "png",
        }

    def _build_inputs(
        self,
        *,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
    ) -> dict:
        if self.input_mapping == "multi_image_edit":
            return self._build_qwen_multi_image_inputs(
                base_image=base_image,
                garment_image=garment_image,
                inpainting_prompt=inpainting_prompt,
            )

        if self.input_mapping == "google_nano_banana":
            return self._build_google_nano_banana_inputs(
                base_image=base_image,
                garment_image=garment_image,
                inpainting_prompt=inpainting_prompt,
            )

        raise ValueError(
            f"Unsupported REPLICATE_PREVIEW_INPUT_MAPPING: {self.input_mapping}"
        )

    def get_model_identifier(self) -> str:
        return self.model_version or self.model

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        """
        Generate a fast preview image using multi-image editing.

        Args:
            base_image: Anonymized user image bytes.
            garment_image: Product garment image bytes.
            inpainting_prompt: Prompt from semantic parser.
            mask: Unused for this backend.
            size: Unused; aspect ratio is matched to the primary image.
        """
        try:
            logger.info(
                "Running Replicate preview generator (model=%s, mapping=%s)...",
                self.model,
                self.input_mapping,
            )

            inputs = self._build_inputs(
                base_image=base_image,
                garment_image=garment_image,
                inpainting_prompt=inpainting_prompt,
            )

            if self.model_version:
                prediction = self.client.predictions.create(
                    version=self.model_version,
                    input=inputs,
                )
            else:
                prediction = self.client.predictions.create(
                    model=self.model,
                    input=inputs,
                )
            logger.info("Prediction created: %s", prediction.id)

            import time

            max_wait = 180
            start_time = time.time()
            poll_interval = 2

            while prediction.status not in ["succeeded", "failed", "canceled"]:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        f"Prediction timeout after {elapsed:.0f}s for {self.model}"
                    )

                if elapsed % 10 < 2:
                    logger.info(
                        "Status: %s (elapsed: %.0fs)", prediction.status, elapsed
                    )
                time.sleep(poll_interval)
                prediction.reload()

            if prediction.status != "succeeded":
                error_msg = getattr(prediction, "error", "Unknown error")
                raise ValueError(f"Prediction failed: {error_msg}")

            output = prediction.output
            if isinstance(output, str):
                output_url = output
            elif isinstance(output, list) and output:
                output_url = output[0]
            else:
                raise ValueError(f"Unexpected output format: {type(output)} - {output}")

            response = httpx.get(output_url, timeout=30.0)
            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.error("Replicate preview generation failed: %s", str(e))
            raise ValueError(f"Image generation failed: {str(e)}")

    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: Optional[str] = None,
        size: str = "1024x1024",
    ) -> str:
        """Generate preview image from base64 inputs and return base64 output."""
        base_image = self._decode_base64_image(base_image_b64)
        garment_image = self._decode_base64_image(garment_image_b64)

        result_bytes = self.generate_tryon(
            base_image=base_image,
            garment_image=garment_image,
            inpainting_prompt=inpainting_prompt,
            mask=None,
            size=size,
        )

        return base64.b64encode(result_bytes).decode("utf-8")


class QwenFastGenerator(ReplicatePreviewGenerator):
    """Backward-compatible alias for the default Replicate preview model."""
