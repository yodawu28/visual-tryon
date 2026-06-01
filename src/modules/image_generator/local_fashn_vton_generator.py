"""
Local command adapter for FASHN VTON Colab/GPU evaluation.

The adapter intentionally shells out through an argument-template command so
the repo is not tied to one upstream inference script shape.
"""

from __future__ import annotations

import base64
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from src.modules.avatar_preview.profile import FashnVtonCategory
from src.modules.image_generator.base import ImageGeneratorBase


class LocalFashnVtonGenerator(ImageGeneratorBase):
    DEFAULT_MODEL = "fashn-ai/fashn-vton-1.5-local"
    DEFAULT_INPUT_MAPPING = "local_fashn_vton"
    DEFAULT_PROMPT_VERSION = "fashn-vton-local-v1"
    PROMPT_VARIANTS = {DEFAULT_PROMPT_VERSION}

    def __init__(
        self,
        *,
        command_template: str | None = None,
        work_dir: Path | None = None,
        timeout_seconds: int = 900,
        model: str = DEFAULT_MODEL,
    ):
        self.command_template = command_template or os.getenv("FASHN_VTON_COMMAND")
        self.work_dir = work_dir
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.input_mapping = self.DEFAULT_INPUT_MAPPING
        self.prompt_variant = self.DEFAULT_PROMPT_VERSION
        self.category = FashnVtonCategory.TOPS

    def set_case_context(
        self,
        *,
        fashn_category: str,
        **_: object,
    ) -> None:
        self.category = FashnVtonCategory(fashn_category)

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

    def get_prompt_version(self) -> str:
        if self.prompt_variant not in self.PROMPT_VARIANTS:
            raise ValueError(
                f"Unsupported FASHN VTON prompt variant: {self.prompt_variant}"
            )
        return self.prompt_variant

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "preview_model": self.model,
            "preview_input_mapping": self.input_mapping,
            "preview_prompt_version": self.get_prompt_version(),
        }

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        if not self.command_template:
            raise ValueError(
                "FASHN VTON command template is required. Set --command-template "
                "or FASHN_VTON_COMMAND."
            )

        with tempfile.TemporaryDirectory(prefix="fashn-vton-eval-") as temp_dir:
            temp_path = Path(temp_dir)
            avatar_path = temp_path / "avatar.png"
            garment_path = temp_path / "garment.png"
            output_path = temp_path / "output.png"
            avatar_path.write_bytes(base_image)
            garment_path.write_bytes(garment_image)

            command_args = self._build_command_args(
                avatar_image=avatar_path,
                garment_image=garment_path,
                output_image=output_path,
                category=self.category,
                prompt=inpainting_prompt,
                size=size,
            )
            result = subprocess.run(
                command_args,
                cwd=self.work_dir,
                timeout=self.timeout_seconds,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "FASHN VTON command failed "
                    f"(exit={result.returncode}): {_tail(result.stderr)}"
                )
            if not output_path.exists():
                raise RuntimeError(
                    "FASHN VTON command finished without writing output image: "
                    f"{output_path}"
                )
            return output_path.read_bytes()

    def _build_command_args(
        self,
        *,
        avatar_image: Path,
        garment_image: Path,
        output_image: Path,
        category: FashnVtonCategory,
        prompt: str,
        size: str,
    ) -> list[str]:
        if self.command_template is None:
            raise ValueError("FASHN VTON command template is required")
        values = {
            "avatar_image": str(avatar_image),
            "garment_image": str(garment_image),
            "output_image": str(output_image),
            "category": category.value,
            "prompt": prompt,
            "size": size,
        }
        return shlex.split(self.command_template.format(**values))

    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: Optional[str] = None,
        size: str = "1024x1024",
    ) -> str:
        result_bytes = self.generate_tryon(
            base_image=self._decode_base64_image(base_image_b64),
            garment_image=self._decode_base64_image(garment_image_b64),
            inpainting_prompt=inpainting_prompt,
            mask=self._decode_base64_image(mask_b64) if mask_b64 else None,
            size=size,
        )
        return base64.b64encode(result_bytes).decode("utf-8")


def _tail(value: str, *, limit: int = 500) -> str:
    compact = value.strip()
    return compact[-limit:] if len(compact) > limit else compact
