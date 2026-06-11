"""Prepare normalized person and garment inputs for local VTON smoke tests."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from PIL import ImageEnhance
from PIL import ImageFilter
from PIL import ImageOps


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-image", required=True, type=Path)
    parser.add_argument("--garment-image", required=True, type=Path)
    parser.add_argument("--person-output", required=True, type=Path)
    parser.add_argument("--garment-output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--person-max-size", type=int, default=1024)
    parser.add_argument("--garment-canvas-size", type=int, default=1024)
    parser.add_argument("--garment-border-ratio", type=float, default=0.08)
    parser.add_argument("--background", default="250,250,250")
    parser.add_argument("--foreground-threshold", type=float, default=28.0)
    parser.add_argument(
        "--person-enhance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply conservative contrast/sharpness normalization to person image",
    )
    parser.add_argument(
        "--garment-enhance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply conservative contrast/sharpness normalization to garment image",
    )
    return parser.parse_args(argv)


def prepare_conditioned_inputs(
    *,
    person_image: Path,
    garment_image: Path,
    person_output: Path,
    garment_output: Path,
    report: Path,
    person_max_size: int,
    garment_canvas_size: int,
    garment_border_ratio: float,
    background: tuple[int, int, int],
    foreground_threshold: float,
    person_enhance: bool,
    garment_enhance: bool,
) -> dict[str, Any]:
    person = _load_image(person_image).convert("RGB")
    garment = _load_image(garment_image).convert("RGBA")

    conditioned_person = _condition_person(
        person,
        max_size=person_max_size,
        enhance=person_enhance,
    )
    conditioned_garment, garment_meta = _condition_garment(
        garment,
        canvas_size=garment_canvas_size,
        border_ratio=garment_border_ratio,
        background=background,
        foreground_threshold=foreground_threshold,
        enhance=garment_enhance,
    )

    person_output.parent.mkdir(parents=True, exist_ok=True)
    garment_output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    conditioned_person.save(person_output, format="PNG")
    conditioned_garment.save(garment_output, format="PNG")

    payload = {
        "success": True,
        "created_at": datetime.now(UTC).isoformat(),
        "person_image": str(person_image),
        "garment_image": str(garment_image),
        "person_output": str(person_output),
        "garment_output": str(garment_output),
        "person": {
            "input_size": list(person.size),
            "output_size": list(conditioned_person.size),
            "max_size": person_max_size,
            "enhance": person_enhance,
        },
        "garment": {
            "input_size": list(garment.size),
            "output_size": list(conditioned_garment.size),
            "canvas_size": garment_canvas_size,
            "border_ratio": garment_border_ratio,
            "background": list(background),
            "foreground_threshold": foreground_threshold,
            "enhance": garment_enhance,
            **garment_meta,
        },
    }
    report.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    return payload


def _load_image(path: Path) -> Image.Image:
    if not path.exists():
        raise FileNotFoundError(f"Input image not found: {path}")
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).copy()


def _condition_person(
    image: Image.Image,
    *,
    max_size: int,
    enhance: bool,
) -> Image.Image:
    image = _resize_max(image, max_size=max_size)
    if not enhance:
        return image
    image = ImageOps.autocontrast(image, cutoff=0.5)
    image = ImageEnhance.Contrast(image).enhance(1.04)
    image = ImageEnhance.Sharpness(image).enhance(1.12)
    return image


def _condition_garment(
    image: Image.Image,
    *,
    canvas_size: int,
    border_ratio: float,
    background: tuple[int, int, int],
    foreground_threshold: float,
    enhance: bool,
) -> tuple[Image.Image, dict[str, Any]]:
    crop_box, mask_ratio = _foreground_bbox(
        image,
        threshold=foreground_threshold,
    )
    warnings: list[str] = []
    if crop_box is None:
        crop_box = (0, 0, image.width, image.height)
        warnings.append("foreground_bbox_not_found")

    crop_box = _expand_box(crop_box, image.size, ratio=border_ratio)
    cropped = image.crop(crop_box)
    cropped = _resize_max(
        cropped, max_size=_inner_canvas_size(canvas_size, border_ratio)
    )

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (*background, 255))
    x = (canvas.width - cropped.width) // 2
    y = (canvas.height - cropped.height) // 2
    canvas.alpha_composite(cropped, (x, y))
    rgb_canvas = canvas.convert("RGB")

    if enhance:
        rgb_canvas = ImageOps.autocontrast(rgb_canvas, cutoff=0.5)
        rgb_canvas = ImageEnhance.Color(rgb_canvas).enhance(1.03)
        rgb_canvas = ImageEnhance.Contrast(rgb_canvas).enhance(1.06)
        rgb_canvas = rgb_canvas.filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=3)
        )

    return rgb_canvas, {
        "crop_box": list(crop_box),
        "foreground_mask_ratio": round(mask_ratio, 4),
        "warnings": warnings,
    }


def _foreground_bbox(
    image: Image.Image,
    *,
    threshold: float,
) -> tuple[tuple[int, int, int, int] | None, float]:
    rgba = np.asarray(image.convert("RGBA")).astype(np.int16)
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3]

    alpha_mask = alpha < 245
    corner_pixels = np.concatenate(
        [
            rgb[:24, :24].reshape(-1, 3),
            rgb[:24, -24:].reshape(-1, 3),
            rgb[-24:, :24].reshape(-1, 3),
            rgb[-24:, -24:].reshape(-1, 3),
        ],
        axis=0,
    )
    background = np.median(corner_pixels, axis=0)
    distance = np.linalg.norm(rgb - background, axis=2)
    color_mask = distance > threshold
    mask = np.logical_or(alpha_mask, color_mask)

    if mask.mean() < 0.002:
        return None, float(mask.mean())

    ys, xs = np.where(mask)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), float(
        mask.mean()
    )


def _expand_box(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
    *,
    ratio: float,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    pad = int(max(width, height) * ratio)
    image_width, image_height = image_size
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(image_width, right + pad),
        min(image_height, bottom + pad),
    )


def _resize_max(image: Image.Image, *, max_size: int) -> Image.Image:
    if max(image.size) <= max_size:
        return image.copy()
    width, height = image.size
    scale = max_size / max(width, height)
    resized = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(resized, Image.Resampling.LANCZOS)


def _inner_canvas_size(canvas_size: int, border_ratio: float) -> int:
    return max(1, round(canvas_size * (1 - (2 * border_ratio))))


def _parse_rgb(value: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("background must be R,G,B")
    try:
        rgb = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("background must be R,G,B") from exc
    if any(channel < 0 or channel > 255 for channel in rgb):
        raise argparse.ArgumentTypeError("background channels must be 0..255")
    return rgb  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = prepare_conditioned_inputs(
        person_image=args.person_image,
        garment_image=args.garment_image,
        person_output=args.person_output,
        garment_output=args.garment_output,
        report=args.report,
        person_max_size=args.person_max_size,
        garment_canvas_size=args.garment_canvas_size,
        garment_border_ratio=args.garment_border_ratio,
        background=_parse_rgb(args.background),
        foreground_threshold=args.foreground_threshold,
        person_enhance=args.person_enhance,
        garment_enhance=args.garment_enhance,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
