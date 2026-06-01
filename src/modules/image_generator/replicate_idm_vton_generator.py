"""
Replicate IDM-VTON generator for eval runs.
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


class ReplicateIdmVtonGenerator(ImageGeneratorBase):
    """
    Dedicated Replicate adapter for cuuupid/idm-vton.

    This uses the model's VTON-specific input schema instead of the generic
    multi-image edit schema used by Qwen/Nano preview models.
    """

    DEFAULT_MODEL = "cuuupid/idm-vton"
    DEFAULT_MODEL_VERSION = (
        "0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985"
    )
    DEFAULT_INPUT_MAPPING = "replicate_idm_vton"
    DEFAULT_PROMPT_VERSION = "idm-vton-v1"
    PROMPT_VARIANTS = {DEFAULT_PROMPT_VERSION}

    def __init__(self):
        settings = get_settings()
        self.model = self.DEFAULT_MODEL
        self.model_version = self.DEFAULT_MODEL_VERSION
        self.input_mapping = self.DEFAULT_INPUT_MAPPING
        self.prompt_variant = self.DEFAULT_PROMPT_VERSION
        self.category = "upper_body"
        self.crop = True
        self.steps = 30
        self.seed = 42
        self.use_mask = False
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

    @staticmethod
    def _detect_category(inpainting_prompt: str) -> str:
        prompt_lower = inpainting_prompt.lower()
        if any(
            keyword in prompt_lower
            for keyword in ["dress", "gown", "one-piece", "one piece"]
        ):
            return "dresses"
        if any(
            keyword in prompt_lower
            for keyword in ["pants", "jeans", "trousers", "shorts", "lower body"]
        ):
            return "lower_body"
        return "upper_body"

    def get_prompt_version(self) -> str:
        if self.prompt_variant not in self.PROMPT_VARIANTS:
            raise ValueError(
                f"Unsupported IDM-VTON prompt variant: {self.prompt_variant}"
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
        category = (
            self._detect_category(inpainting_prompt)
            if self.category == "auto"
            else self.category
        )
        inputs = {
            "human_img": self._named_image_io(base_image, "human.png"),
            "garm_img": self._named_image_io(garment_image, "garment.png"),
            "garment_des": inpainting_prompt,
            "category": category,
            "crop": self.crop,
            "seed": self.seed,
            "steps": self.steps,
        }
        if self.use_mask and mask is not None:
            inputs["mask_img"] = self._named_image_io(mask, "mask.png")
        return inputs

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
                "Running Replicate IDM-VTON generator (model=%s, version=%s)...",
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
            logger.error("Replicate IDM-VTON generation failed: %s", str(exc))
            raise ValueError(f"Image generation failed: {str(exc)}") from exc

    @staticmethod
    def _read_output(output: object) -> bytes:
        if hasattr(output, "read"):
            return output.read()

        if hasattr(output, "url"):
            output = getattr(output, "url")

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
