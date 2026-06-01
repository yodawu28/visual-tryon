"""
Replicate Flux Kontext multi-image generator for creative outfit previews.
"""

from __future__ import annotations

import base64
import io
import logging
import re
import time
from typing import Optional

import httpx
from replicate import Client

from src.config.settings import get_settings
from src.modules.image_generator.base import ImageGeneratorBase

logger = logging.getLogger(__name__)


class ReplicateFluxKontextGenerator(ImageGeneratorBase):
    """
    Dedicated Replicate adapter for flux-kontext-apps/multi-image-kontext-pro.

    This is not a true VTO model. It is used only for the pivoted "creative
    outfit preview" path where latency/warm availability matters more than
    strict garment transfer.
    """

    DEFAULT_MODEL = "flux-kontext-apps/multi-image-kontext-pro"
    DEFAULT_MODEL_VERSION = None
    DEFAULT_INPUT_MAPPING = "flux_kontext_multi_image"
    DEFAULT_PROMPT_VERSION = "flux-kontext-outfit-preview-v1"
    PROMPT_VARIANTS = {DEFAULT_PROMPT_VERSION}

    def __init__(self):
        settings = get_settings()
        self.model = self.DEFAULT_MODEL
        self.model_version = self.DEFAULT_MODEL_VERSION
        self.input_mapping = self.DEFAULT_INPUT_MAPPING
        self.prompt_variant = self.DEFAULT_PROMPT_VERSION
        self.aspect_ratio = "match_input_image"
        self.output_format = "png"
        self.safety_tolerance = 2
        self.seed = 42
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

    def get_prompt_version(self) -> str:
        if self.prompt_variant not in self.PROMPT_VARIANTS:
            raise ValueError(
                f"Unsupported Flux Kontext prompt variant: {self.prompt_variant}"
            )
        return self.prompt_variant

    def get_model_identifier(self) -> str:
        return self.model_version or self.model

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "preview_model": self.get_model_identifier(),
            "preview_input_mapping": self.input_mapping,
            "preview_prompt_version": self.get_prompt_version(),
        }

    def _build_prompt(self, inpainting_prompt: str) -> str:
        self.get_prompt_version()
        return (
            "Create a creative outfit preview. "
            "Use image 1 as the base person photo and image 2 as the garment reference. "
            "Make the anonymized person in image 1 wear the garment from image 2. "
            "Preserve the person, anonymized face area, body pose, camera framing, "
            "background, lighting, and overall photo texture as much as possible. "
            "Prioritize a plausible editorial outfit preview over a strict technical "
            "virtual try-on. "
            "Preserve the garment color palette, silhouette, sleeve length, collar, "
            "logos, text, stripes, panels, trims, and visible design details as much "
            "as the model can. "
            "Do not create a new person, do not change the background, and do not "
            "remove the anonymized face blur. "
            f"Garment/context details: {inpainting_prompt}"
        )

    def _build_inputs(
        self,
        *,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: bytes | None,
    ) -> dict:
        return {
            "input_image_1": self._named_image_io(base_image, "user.png"),
            "input_image_2": self._named_image_io(garment_image, "garment.png"),
            "prompt": self._build_prompt(inpainting_prompt),
            "aspect_ratio": self.aspect_ratio,
            "output_format": self.output_format,
            "safety_tolerance": self.safety_tolerance,
            "seed": self.seed,
        }

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        try:
            logger.info(
                "Running Replicate Flux Kontext generator (model=%s, version=%s)...",
                self.model,
                self.model_version,
            )
            inputs = self._build_inputs(
                base_image=base_image,
                garment_image=garment_image,
                inpainting_prompt=inpainting_prompt,
                mask=mask,
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

            max_wait = 180
            start_time = time.time()
            poll_interval = 2

            while prediction.status not in ["succeeded", "failed", "canceled"]:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        f"Prediction timeout after {elapsed:.0f}s for {self.model}"
                    )
                if elapsed % 10 < poll_interval:
                    logger.info(
                        "Status: %s (elapsed: %.0fs)",
                        prediction.status,
                        elapsed,
                    )
                time.sleep(poll_interval)
                prediction.reload()

            if prediction.status != "succeeded":
                error_msg = getattr(prediction, "error", "Unknown error")
                raise ValueError(f"Prediction failed: {error_msg}")

            return self._read_output(prediction.output)
        except Exception as exc:
            logger.error("Replicate Flux Kontext generation failed: %s", str(exc))
            raise ValueError(f"Image generation failed: {str(exc)}") from exc

    @staticmethod
    def _read_output(output: object) -> bytes:
        if hasattr(output, "read"):
            return output.read()

        if hasattr(output, "url"):
            output_url = getattr(output, "url")
            output = output_url() if callable(output_url) else output_url

        if isinstance(output, list) and output:
            output = output[0]
            if hasattr(output, "read"):
                return output.read()
            if hasattr(output, "url"):
                output_url = getattr(output, "url")
                output = output_url() if callable(output_url) else output_url

        if isinstance(output, str):
            response = httpx.get(output, timeout=30.0)
            response.raise_for_status()
            return response.content

        raise ValueError(f"Unexpected output format: {type(output)} - {output}")

    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: Optional[str] = None,
        size: str = "1024x1024",
    ) -> str:
        base_image = self._decode_base64_image(base_image_b64)
        garment_image = self._decode_base64_image(garment_image_b64)
        mask = self._decode_base64_image(mask_b64) if mask_b64 else None

        result_bytes = self.generate_tryon(
            base_image=base_image,
            garment_image=garment_image,
            inpainting_prompt=inpainting_prompt,
            mask=mask,
            size=size,
        )
        return base64.b64encode(result_bytes).decode("utf-8")
