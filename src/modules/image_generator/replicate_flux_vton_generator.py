"""
Replicate Flux-VTON generator for eval runs.
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


class ReplicateFluxVtonGenerator(ImageGeneratorBase):
    """
    Dedicated Replicate adapter for subhash25rawat/flux-vton.

    This model uses a minimal VTON-specific schema: subject image, garment image,
    and garment part. It does not accept a text prompt.
    """

    DEFAULT_MODEL = "subhash25rawat/flux-vton"
    DEFAULT_MODEL_VERSION = (
        "a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199"
    )
    DEFAULT_INPUT_MAPPING = "replicate_flux_vton"
    DEFAULT_PROMPT_VERSION = "flux-vton-v1"
    PROMPT_VARIANTS = {DEFAULT_PROMPT_VERSION}

    def __init__(self):
        settings = get_settings()
        self.model = self.DEFAULT_MODEL
        self.model_version = self.DEFAULT_MODEL_VERSION
        self.input_mapping = self.DEFAULT_INPUT_MAPPING
        self.prompt_variant = self.DEFAULT_PROMPT_VERSION
        self.part = "upper_body"
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
                f"Unsupported Flux-VTON prompt variant: {self.prompt_variant}"
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

    def _build_inputs(
        self,
        *,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: bytes | None,
    ) -> dict:
        return {
            "image": self._named_image_io(base_image, "subject.png"),
            "garment": self._named_image_io(garment_image, "garment.png"),
            "part": self.part,
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
                "Running Replicate Flux-VTON generator (model=%s, version=%s)...",
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

            max_wait = 420
            start_time = time.time()
            poll_interval = 3

            while prediction.status not in ["succeeded", "failed", "canceled"]:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        f"Prediction timeout after {elapsed:.0f}s for {self.model}"
                    )
                if elapsed % 15 < poll_interval:
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
            logger.error("Replicate Flux-VTON generation failed: %s", str(exc))
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
