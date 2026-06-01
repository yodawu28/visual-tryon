"""
Replicate text-to-image generator for privacy-safe synthetic human avatars.
"""

from __future__ import annotations

import base64
import logging
import time

import httpx
from replicate import Client

from src.config.settings import get_settings
from src.modules.avatar_preview.prompt_builder import AVATAR_PROMPT_VERSION
from src.modules.image_generator.replicate_rate_limit import (
    create_prediction_with_rate_limit_retry,
)

logger = logging.getLogger(__name__)


class ReplicateSyntheticAvatarGenerator:
    """Generate a reusable synthetic human avatar from a body-profile prompt."""

    DEFAULT_MODEL = "black-forest-labs/flux-schnell"
    DEFAULT_MODEL_VERSION = None
    DEFAULT_CATALOG_VERSION = "generated-synthetic-person-photo-v1"

    def __init__(self):
        settings = get_settings()
        self.model = self.DEFAULT_MODEL
        self.model_version = self.DEFAULT_MODEL_VERSION
        self.avatar_catalog_version = self.DEFAULT_CATALOG_VERSION
        self.aspect_ratio = "1:1"
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

    def get_model_identifier(self) -> str:
        return self.model_version or self.model

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "avatar_model": self.get_model_identifier(),
            "avatar_catalog_version": self.avatar_catalog_version,
            "avatar_prompt_version": AVATAR_PROMPT_VERSION,
        }

    def _build_inputs(self, prompt: str) -> dict[str, object]:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Avatar generation prompt is empty")

        return {
            "prompt": normalized_prompt,
            "aspect_ratio": self.aspect_ratio,
            "output_format": self.output_format,
            "safety_tolerance": self.safety_tolerance,
            "seed": self.seed,
        }

    def generate_avatar(self, *, prompt: str, size: str = "1024x1024") -> str:
        try:
            logger.info(
                "Running Replicate synthetic avatar generator (model=%s, version=%s)",
                self.model,
                self.model_version,
            )
            inputs = self._build_inputs(prompt)
            if self.model_version:
                prediction = create_prediction_with_rate_limit_retry(
                    lambda: self.client.predictions.create(
                        version=self.model_version,
                        input=inputs,
                    )
                )
            else:
                prediction = create_prediction_with_rate_limit_retry(
                    lambda: self.client.predictions.create(
                        model=self.model,
                        input=inputs,
                    )
                )

            max_wait = 180
            start_time = time.time()
            poll_interval = 2
            while prediction.status not in ["succeeded", "failed", "canceled"]:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(
                        f"Prediction timeout after {elapsed:.0f}s for {self.model}"
                    )
                time.sleep(poll_interval)
                prediction.reload()

            if prediction.status != "succeeded":
                error_msg = getattr(prediction, "error", "Unknown error")
                raise ValueError(f"Prediction failed: {error_msg}")

            avatar_bytes = self._read_output(prediction.output)
            return base64.b64encode(avatar_bytes).decode("utf-8")
        except Exception as exc:
            logger.error("Replicate synthetic avatar generation failed: %s", str(exc))
            raise ValueError(f"Avatar generation failed: {str(exc)}") from exc

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

        raise ValueError(f"Unexpected avatar output format: {type(output)} - {output}")
