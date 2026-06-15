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
    parser.add_argument("--person-canvas-size", default="768x1024")
    parser.add_argument("--person-border-ratio", type=float, default=0.06)
    parser.add_argument(
        "--person-framing",
        choices=("full_body", "upper_body"),
        default="full_body",
        help="Condition person as full body or upper-body focused crop",
    )
    parser.add_argument("--garment-canvas-size", type=int, default=1024)
    parser.add_argument("--garment-border-ratio", type=float, default=0.08)
    parser.add_argument(
        "--garment-largest-component",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Crop around the largest garment-like foreground component",
    )
    parser.add_argument("--background", default="250,250,250")
    parser.add_argument("--foreground-threshold", type=float, default=28.0)
    parser.add_argument(
        "--person-clean-background",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Crop the person foreground and place it on a clean background",
    )
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
    person_canvas_size: tuple[int, int],
    person_border_ratio: float,
    person_framing: str,
    garment_canvas_size: int,
    garment_border_ratio: float,
    garment_largest_component: bool,
    background: tuple[int, int, int],
    foreground_threshold: float,
    person_clean_background: bool,
    person_enhance: bool,
    garment_enhance: bool,
) -> dict[str, Any]:
    person = _load_image(person_image).convert("RGB")
    garment = _load_image(garment_image).convert("RGBA")

    conditioned_person = _condition_person(
        person,
        max_size=person_max_size,
        canvas_size=person_canvas_size,
        border_ratio=person_border_ratio,
        framing=person_framing,
        background=background,
        foreground_threshold=foreground_threshold,
        clean_background=person_clean_background,
        enhance=person_enhance,
    )
    conditioned_person, person_meta = conditioned_person
    conditioned_garment, garment_meta = _condition_garment(
        garment,
        canvas_size=garment_canvas_size,
        border_ratio=garment_border_ratio,
        largest_component=garment_largest_component,
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
            "canvas_size": list(person_canvas_size),
            "border_ratio": person_border_ratio,
            "framing": person_framing,
            "background": list(background),
            "clean_background": person_clean_background,
            "foreground_threshold": foreground_threshold,
            "enhance": person_enhance,
            **person_meta,
        },
        "garment": {
            "input_size": list(garment.size),
            "output_size": list(conditioned_garment.size),
            "canvas_size": garment_canvas_size,
            "border_ratio": garment_border_ratio,
            "largest_component": garment_largest_component,
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
    canvas_size: tuple[int, int],
    border_ratio: float,
    framing: str,
    background: tuple[int, int, int],
    foreground_threshold: float,
    clean_background: bool,
    enhance: bool,
) -> tuple[Image.Image, dict[str, Any]]:
    meta: dict[str, Any] = {"warnings": []}
    if clean_background:
        foreground_mask = _foreground_mask(
            image,
            threshold=foreground_threshold,
        )
        component_mask = _largest_component_mask(foreground_mask)
        if component_mask is None:
            component_mask = foreground_mask
            meta["warnings"].append("person_largest_component_not_found")
        component_mask = _clean_component_mask(component_mask)
        crop_box, mask_ratio = _bbox_from_mask(component_mask)
        meta["foreground_mask_ratio"] = round(mask_ratio, 4)
        if crop_box is None:
            crop_box = (0, 0, image.width, image.height)
            meta["warnings"].append("person_foreground_bbox_not_found")
        full_body_box = crop_box
        if framing == "upper_body":
            crop_box = _upper_body_box(crop_box, image.size)
            meta["upper_body_from_box"] = list(full_body_box)
        crop_box = _expand_box(crop_box, image.size, ratio=border_ratio)
        crop_mask = component_mask[crop_box[1] : crop_box[3], crop_box[0] : crop_box[2]]
        cropped = image.crop(crop_box)
        mask_image = Image.fromarray(crop_mask.astype("uint8") * 255)
        resized_image = _resize_to_fit_canvas(
            cropped,
            canvas_size=canvas_size,
            border_ratio=border_ratio,
        )
        resized_mask = mask_image.resize(resized_image.size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", canvas_size, background)
        x = (canvas.width - resized_image.width) // 2
        y = (canvas.height - resized_image.height) // 2
        paste_width, paste_height = resized_image.size
        canvas.paste(resized_image, (x, y), resized_mask)
        image = canvas
        meta["crop_box"] = list(crop_box)
        meta["paste_box"] = [x, y, x + paste_width, y + paste_height]
        meta.update(
            _person_quality_metrics(
                original_size=image.size,
                foreground_box=full_body_box,
                crop_box=crop_box,
                paste_box=(x, y, x + paste_width, y + paste_height),
                canvas_size=canvas_size,
                framing=framing,
            )
        )
    else:
        image = _resize_max(image, max_size=max_size)
        meta.update(
            _person_quality_metrics(
                original_size=image.size,
                foreground_box=(0, 0, image.width, image.height),
                crop_box=(0, 0, image.width, image.height),
                paste_box=(0, 0, image.width, image.height),
                canvas_size=image.size,
                framing=framing,
            )
        )

    if not enhance:
        return image, meta
    image = ImageOps.autocontrast(image, cutoff=0.5)
    image = ImageEnhance.Contrast(image).enhance(1.04)
    image = ImageEnhance.Sharpness(image).enhance(1.12)
    return image, meta


def _condition_garment(
    image: Image.Image,
    *,
    canvas_size: int,
    border_ratio: float,
    largest_component: bool,
    background: tuple[int, int, int],
    foreground_threshold: float,
    enhance: bool,
) -> tuple[Image.Image, dict[str, Any]]:
    warnings: list[str] = []
    component_mask: np.ndarray | None = None
    if largest_component:
        foreground_mask = _foreground_mask(image, threshold=foreground_threshold)
        component_mask = _largest_component_mask(foreground_mask)
        if component_mask is None:
            warnings.append("garment_largest_component_not_found")
        else:
            component_mask = _clean_component_mask(component_mask)
            crop_box, mask_ratio = _bbox_from_mask(component_mask)
    if component_mask is None:
        crop_box, mask_ratio = _foreground_bbox(
            image,
            threshold=foreground_threshold,
        )

    if crop_box is None:
        crop_box = (0, 0, image.width, image.height)
        warnings.append("foreground_bbox_not_found")

    crop_box = _expand_box(crop_box, image.size, ratio=border_ratio)
    cropped = image.crop(crop_box)
    cropped_mask = None
    if component_mask is not None:
        crop_mask = component_mask[crop_box[1] : crop_box[3], crop_box[0] : crop_box[2]]
        cropped_mask = Image.fromarray(crop_mask.astype("uint8") * 255)

    original_cropped_size = cropped.size
    cropped = _resize_max(
        cropped, max_size=_inner_canvas_size(canvas_size, border_ratio)
    )
    if cropped_mask is not None and cropped.size != original_cropped_size:
        cropped_mask = cropped_mask.resize(cropped.size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (*background, 255))
    x = (canvas.width - cropped.width) // 2
    y = (canvas.height - cropped.height) // 2
    if cropped_mask is not None:
        canvas.paste(cropped, (x, y), cropped_mask)
    else:
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
    largest_component: bool = False,
) -> tuple[tuple[int, int, int, int] | None, float]:
    mask = _foreground_mask(image, threshold=threshold)

    if largest_component:
        component_mask = _largest_component_mask(mask)
        if component_mask is not None:
            mask = component_mask

    return _bbox_from_mask(mask)


def _bbox_from_mask(mask: np.ndarray) -> tuple[tuple[int, int, int, int] | None, float]:
    if mask.mean() < 0.002:
        return None, float(mask.mean())

    ys, xs = np.where(mask)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), float(
        mask.mean()
    )


def _foreground_mask(
    image: Image.Image,
    *,
    threshold: float,
) -> np.ndarray:
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
    return np.logical_or(alpha_mask, color_mask)


def _largest_component_mask(mask: np.ndarray) -> np.ndarray | None:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return None

    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask.astype("uint8"), connectivity=8
    )
    if num_labels <= 1:
        return None

    min_area = max(64, int(mask.size * 0.005))
    best_label = 0
    best_area = 0
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= min_area and area > best_area:
            best_label = label
            best_area = area

    if best_label == 0:
        return None
    return labels == best_label


def _clean_component_mask(mask: np.ndarray) -> np.ndarray:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return mask

    mask_uint8 = mask.astype("uint8") * 255
    kernel = np.ones((9, 9), np.uint8)
    closed = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel, iterations=2)
    dilated = cv2.dilate(closed, kernel, iterations=1)
    return dilated > 0


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


def _upper_body_box(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    height = bottom - top
    upper_bottom = top + round(height * 0.58)
    image_width, image_height = image_size
    width = right - left
    horizontal_pad = round(width * 0.08)
    top_pad = round(height * 0.03)
    bottom_pad = round(height * 0.06)
    return (
        max(0, left - horizontal_pad),
        max(0, top - top_pad),
        min(image_width, right + horizontal_pad),
        min(image_height, upper_bottom + bottom_pad),
    )


def _person_quality_metrics(
    *,
    original_size: tuple[int, int],
    foreground_box: tuple[int, int, int, int],
    crop_box: tuple[int, int, int, int],
    paste_box: tuple[int, int, int, int],
    canvas_size: tuple[int, int],
    framing: str,
) -> dict[str, Any]:
    original_width, original_height = original_size
    canvas_width, canvas_height = canvas_size
    fg_width = max(1, foreground_box[2] - foreground_box[0])
    fg_height = max(1, foreground_box[3] - foreground_box[1])
    crop_width = max(1, crop_box[2] - crop_box[0])
    crop_height = max(1, crop_box[3] - crop_box[1])
    paste_width = max(1, paste_box[2] - paste_box[0])
    paste_height = max(1, paste_box[3] - paste_box[1])

    torso_top = foreground_box[1] + round(fg_height * 0.22)
    torso_bottom = foreground_box[1] + round(fg_height * 0.58)
    torso_width = fg_width * 0.62
    torso_height = max(1, torso_bottom - torso_top)
    source_torso_pixels = torso_width * torso_height
    scale_x = paste_width / crop_width
    scale_y = paste_height / crop_height
    output_torso_pixels = source_torso_pixels * scale_x * scale_y
    output_torso_width = torso_width * scale_x
    output_torso_height = torso_height * scale_y

    body_canvas_height_ratio = paste_height / canvas_height
    body_canvas_width_ratio = paste_width / canvas_width
    torso_canvas_area_ratio = output_torso_pixels / (canvas_width * canvas_height)
    estimated_logo_width_px = output_torso_width * 0.45

    score_parts = [
        _score_range(
            body_canvas_height_ratio,
            low=0.7 if framing == "full_body" else 0.72,
            high=0.95,
        ),
        _score_min(
            torso_canvas_area_ratio, target=0.13 if framing == "upper_body" else 0.055
        ),
        _score_min(estimated_logo_width_px, target=180),
    ]
    framing_score = round(sum(score_parts) / len(score_parts), 4)

    return {
        "quality_metrics": {
            "body_canvas_height_ratio": round(body_canvas_height_ratio, 4),
            "body_canvas_width_ratio": round(body_canvas_width_ratio, 4),
            "source_torso_pixels_estimate": round(source_torso_pixels, 2),
            "output_torso_pixels_estimate": round(output_torso_pixels, 2),
            "output_torso_width_px_estimate": round(output_torso_width, 2),
            "output_torso_height_px_estimate": round(output_torso_height, 2),
            "torso_canvas_area_ratio_estimate": round(torso_canvas_area_ratio, 4),
            "estimated_logo_width_px": round(estimated_logo_width_px, 2),
            "vton_input_framing_score": framing_score,
        },
        "quality_warnings": _quality_warnings(
            framing=framing,
            body_canvas_height_ratio=body_canvas_height_ratio,
            torso_canvas_area_ratio=torso_canvas_area_ratio,
            estimated_logo_width_px=estimated_logo_width_px,
        ),
    }


def _score_min(value: float, *, target: float) -> float:
    return max(0.0, min(1.0, value / target))


def _score_range(value: float, *, low: float, high: float) -> float:
    if low <= value <= high:
        return 1.0
    if value < low:
        return max(0.0, value / low)
    return max(0.0, 1.0 - ((value - high) / max(0.001, 1 - high)))


def _quality_warnings(
    *,
    framing: str,
    body_canvas_height_ratio: float,
    torso_canvas_area_ratio: float,
    estimated_logo_width_px: float,
) -> list[str]:
    warnings: list[str] = []
    min_torso_area = 0.13 if framing == "upper_body" else 0.055
    min_body_height = 0.72 if framing == "upper_body" else 0.7
    if body_canvas_height_ratio < min_body_height:
        warnings.append("person_too_small_for_vton")
    if torso_canvas_area_ratio < min_torso_area:
        warnings.append("torso_region_too_small_for_garment_detail")
    if estimated_logo_width_px < 180:
        warnings.append("estimated_logo_region_low_resolution")
    return warnings


def _resize_max(image: Image.Image, *, max_size: int) -> Image.Image:
    if max(image.size) <= max_size:
        return image.copy()
    width, height = image.size
    scale = max_size / max(width, height)
    resized = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(resized, Image.Resampling.LANCZOS)


def _resize_to_fit_canvas(
    image: Image.Image,
    *,
    canvas_size: tuple[int, int],
    border_ratio: float,
) -> Image.Image:
    canvas_width, canvas_height = canvas_size
    max_width = max(1, round(canvas_width * (1 - (2 * border_ratio))))
    max_height = max(1, round(canvas_height * (1 - (2 * border_ratio))))
    scale = min(max_width / image.width, max_height / image.height)
    resized = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(resized, Image.Resampling.LANCZOS)


def _inner_canvas_size(canvas_size: int, border_ratio: float) -> int:
    return max(1, round(canvas_size * (1 - (2 * border_ratio))))


def _parse_size(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in value.lower().split("x")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT")
    try:
        width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size dimensions must be positive")
    return width, height


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
    red, green, blue = rgb
    return red, green, blue


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = prepare_conditioned_inputs(
        person_image=args.person_image,
        garment_image=args.garment_image,
        person_output=args.person_output,
        garment_output=args.garment_output,
        report=args.report,
        person_max_size=args.person_max_size,
        person_canvas_size=_parse_size(args.person_canvas_size),
        person_border_ratio=args.person_border_ratio,
        person_framing=args.person_framing,
        garment_canvas_size=args.garment_canvas_size,
        garment_border_ratio=args.garment_border_ratio,
        garment_largest_component=args.garment_largest_component,
        background=_parse_rgb(args.background),
        foreground_threshold=args.foreground_threshold,
        person_clean_background=args.person_clean_background,
        person_enhance=args.person_enhance,
        garment_enhance=args.garment_enhance,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
