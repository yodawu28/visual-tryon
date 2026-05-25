"""
Local VTO CLI helpers used by smoke tests and manual pipeline runs.
"""

from __future__ import annotations

import argparse
import base64
import io

from PIL import Image, ImageDraw


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local virtual try-on")
    parser.add_argument("--person")
    parser.add_argument("--person-base64")
    parser.add_argument("--mask")
    parser.add_argument("--mask-base64")
    parser.add_argument("--garment")
    parser.add_argument("--garment-base64")
    parser.add_argument("--prompt")
    parser.add_argument("--auto-mask", choices=["full", "upper-body"])
    parser.add_argument("--num-inference-steps", type=int, default=30)
    parser.add_argument("--guidance-scale", type=float, default=7.5)
    parser.add_argument(
        "--negative-prompt",
        default="deformed, bad anatomy, blurry, naked, NSFW, low quality",
    )
    parser.add_argument(
        "--disable-safety-checker",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def load_rgb_image_from_base64(image_b64: str, *, field_name: str) -> Image.Image:
    normalized = image_b64.strip()
    if normalized.startswith("data:"):
        try:
            normalized = normalized.split("base64,", 1)[1]
        except IndexError as exc:
            raise ValueError(f"Invalid base64 data URL for {field_name}") from exc

    try:
        image_bytes = base64.b64decode(normalized, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 payload for {field_name}") from exc

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.convert("RGB")
    except Exception as exc:
        raise ValueError(f"Invalid image payload for {field_name}") from exc


def resize_for_pipeline(image: Image.Image, *, size: int = 512) -> Image.Image:
    return image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)


def create_auto_mask(person: Image.Image, *, mode: str) -> Image.Image:
    if mode == "full":
        return Image.new("L", person.size, color=255)

    if mode != "upper-body":
        raise ValueError(f"Unsupported auto-mask mode: {mode}")

    width, height = person.size
    mask = Image.new("L", person.size, color=0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle(
        (
            int(width * 0.25),
            int(height * 0.30),
            int(width * 0.75),
            int(height * 0.82),
        ),
        fill=255,
    )
    return mask
