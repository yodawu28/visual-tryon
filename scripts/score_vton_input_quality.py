"""Score whether person/garment inputs are good enough for local VTON smoke."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from PIL import ImageFilter
from PIL import ImageOps

from scripts.prepare_vton_conditioned_inputs import _bbox_from_mask
from scripts.prepare_vton_conditioned_inputs import _clean_component_mask
from scripts.prepare_vton_conditioned_inputs import _foreground_mask
from scripts.prepare_vton_conditioned_inputs import _largest_component_mask
from scripts.prepare_vton_conditioned_inputs import _parse_rgb


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person-image", required=True, type=Path)
    parser.add_argument("--garment-image", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--background", default="250,250,250")
    parser.add_argument("--foreground-threshold", type=float, default=28.0)
    return parser.parse_args(argv)


def score_inputs(
    *,
    person_image: Path,
    garment_image: Path,
    background: tuple[int, int, int],
    foreground_threshold: float,
) -> dict[str, Any]:
    person = _load_image(person_image).convert("RGB")
    garment = _load_image(garment_image).convert("RGBA")
    person_mask = _foreground_mask(person, threshold=foreground_threshold)
    person_component = _largest_component_mask(person_mask)
    if person_component is not None:
        person_mask = _clean_component_mask(person_component)
    person_box, person_ratio = _bbox_from_mask(person_mask)
    if person_box is None:
        person_box = (0, 0, person.width, person.height)

    garment_mask = _foreground_mask(garment, threshold=foreground_threshold)
    garment_component = _largest_component_mask(garment_mask)
    if garment_component is not None:
        garment_mask = _clean_component_mask(garment_component)
    garment_box, garment_ratio = _bbox_from_mask(garment_mask)
    if garment_box is None:
        garment_box = (0, 0, garment.width, garment.height)

    person_metrics = _person_metrics(person, person_box, person_ratio)
    garment_metrics = _garment_metrics(garment, garment_box, garment_ratio)
    checks = {
        "person_sharp_enough": person_metrics["blur_variance"] >= 60,
        "person_brightness_ok": 35 <= person_metrics["brightness"] <= 235,
        "person_not_too_small": person_metrics["person_height_ratio"] >= 0.65,
        "torso_detail_enough": person_metrics["estimated_logo_width_px"] >= 180,
        "garment_sharp_enough": garment_metrics["blur_variance"] >= 80,
        "garment_large_enough": garment_metrics["garment_area_ratio"] >= 0.12,
        "garment_background_clean_enough": garment_metrics["foreground_mask_ratio"]
        >= 0.10,
    }
    score = round(sum(1 for value in checks.values() if value) / len(checks), 4)
    return {
        "success": True,
        "created_at": datetime.now(UTC).isoformat(),
        "person_image": str(person_image),
        "garment_image": str(garment_image),
        "background": list(background),
        "foreground_threshold": foreground_threshold,
        "score": score,
        "passed": score >= 0.85,
        "checks": checks,
        "person": person_metrics,
        "garment": garment_metrics,
        "issues": [key for key, passed in checks.items() if not passed],
    }


def _load_image(path: Path) -> Image.Image:
    if not path.exists():
        raise FileNotFoundError(f"Input image not found: {path}")
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).copy()


def _person_metrics(
    image: Image.Image,
    person_box: tuple[int, int, int, int],
    foreground_ratio: float,
) -> dict[str, Any]:
    left, top, right, bottom = person_box
    width = max(1, right - left)
    height = max(1, bottom - top)
    torso_width = width * 0.62
    torso_height = height * 0.36
    estimated_logo_width_px = torso_width * 0.45
    return {
        "input_size": list(image.size),
        "person_box": list(person_box),
        "foreground_mask_ratio": round(foreground_ratio, 4),
        "person_height_ratio": round(height / image.height, 4),
        "person_width_ratio": round(width / image.width, 4),
        "torso_area_ratio_estimate": round(
            (torso_width * torso_height) / (image.width * image.height), 4
        ),
        "estimated_logo_width_px": round(estimated_logo_width_px, 2),
        "blur_variance": round(_blur_variance(image), 4),
        "brightness": round(_brightness(image), 4),
    }


def _garment_metrics(
    image: Image.Image,
    garment_box: tuple[int, int, int, int],
    foreground_ratio: float,
) -> dict[str, Any]:
    left, top, right, bottom = garment_box
    width = max(1, right - left)
    height = max(1, bottom - top)
    return {
        "input_size": list(image.size),
        "garment_box": list(garment_box),
        "foreground_mask_ratio": round(foreground_ratio, 4),
        "garment_width_ratio": round(width / image.width, 4),
        "garment_height_ratio": round(height / image.height, 4),
        "garment_area_ratio": round((width * height) / (image.width * image.height), 4),
        "blur_variance": round(_blur_variance(image.convert("RGB")), 4),
        "brightness": round(_brightness(image.convert("RGB")), 4),
    }


def _blur_variance(image: Image.Image) -> float:
    grayscale = np.asarray(image.convert("L"), dtype=np.float32)
    edges = np.asarray(Image.fromarray(grayscale).filter(ImageFilter.FIND_EDGES))
    return float(np.var(edges))


def _brightness(image: Image.Image) -> float:
    return float(np.mean(np.asarray(image.convert("L"), dtype=np.float32)))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = score_inputs(
        person_image=args.person_image,
        garment_image=args.garment_image,
        background=_parse_rgb(args.background),
        foreground_threshold=args.foreground_threshold,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
