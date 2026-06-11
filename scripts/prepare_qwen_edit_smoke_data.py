"""Prepare deterministic local image inputs for Qwen image-edit smoke tests."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


DEFAULT_SESSION_STEM = "kiosk-session-v1-smoke"
DEFAULT_GARMENT_STEM = "garment-v1-smoke"
DEFAULT_FIXTURE_DIR = Path("examples/qwen_edit_smoke")
DEFAULT_GARMENT_CATEGORY = "upper"


@dataclass(frozen=True)
class SmokeDataPaths:
    person_image: Path
    garment_image: Path
    manifest: Path
    conditioned_person_image: Path
    conditioned_garment_image: Path
    conditioning_report: Path


def prepare_qwen_edit_smoke_data(
    *,
    data_dir: Path,
    fixture_dir: Path = DEFAULT_FIXTURE_DIR,
    session_stem: str = DEFAULT_SESSION_STEM,
    garment_stem: str = DEFAULT_GARMENT_STEM,
    garment_category: str = DEFAULT_GARMENT_CATEGORY,
    overwrite: bool = False,
) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    fixture_dir = fixture_dir.resolve()
    paths = SmokeDataPaths(
        person_image=data_dir
        / "kiosk_sessions"
        / "captures"
        / f"{session_stem}-front.png",
        garment_image=data_dir / "garments" / "images" / f"{garment_stem}.webp",
        manifest=data_dir / "qwen_edit_smoke" / "inputs" / "manifest.json",
        conditioned_person_image=data_dir / "vton_conditioned" / "person-front.png",
        conditioned_garment_image=data_dir / "vton_conditioned" / "garment.png",
        conditioning_report=data_dir / "vton_conditioned" / "report.json",
    )

    for path in (
        paths.person_image,
        paths.garment_image,
        paths.manifest,
        paths.conditioned_person_image,
        paths.conditioned_garment_image,
        paths.conditioning_report,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    fixture_sources = _fixture_sources(fixture_dir)
    if overwrite or not paths.person_image.exists():
        if fixture_sources["person_image"].exists():
            shutil.copyfile(fixture_sources["person_image"], paths.person_image)
        else:
            _create_person_capture(paths.person_image)
        created.append(str(paths.person_image))

    if overwrite or not paths.garment_image.exists():
        if fixture_sources["garment_image"].exists():
            shutil.copyfile(fixture_sources["garment_image"], paths.garment_image)
        else:
            _create_garment_image(paths.garment_image)
        created.append(str(paths.garment_image))

    payload = {
        "fixture_dir": str(fixture_dir),
        "fixture_sources": {
            "person_image": str(fixture_sources["person_image"]),
            "person_image_exists": fixture_sources["person_image"].exists(),
            "garment_image": str(fixture_sources["garment_image"]),
            "garment_image_exists": fixture_sources["garment_image"].exists(),
        },
        "person_image": str(paths.person_image),
        "garment_image": str(paths.garment_image),
        "garment_category": garment_category,
        "catvton_cloth_type": garment_category,
        "leffa_garment_type": _leffa_garment_type(garment_category),
        "smoke_command": (
            "make runpod-qwen-edit-smoke "
            f"PERSON_IMAGE={paths.person_image} "
            f"GARMENT_IMAGE={paths.garment_image}"
        ),
        "catvton_smoke_command": (
            "make runpod-catvton-smoke "
            f"RUNPOD_CATVTON_CLOTH_TYPE={garment_category} "
            f"PERSON_IMAGE={paths.person_image} "
            f"GARMENT_IMAGE={paths.garment_image}"
        ),
        "leffa_smoke_command": (
            "make runpod-leffa-smoke "
            f"RUNPOD_LEFFA_GARMENT_TYPE={_leffa_garment_type(garment_category)} "
            f"PERSON_IMAGE={paths.person_image} "
            f"GARMENT_IMAGE={paths.garment_image}"
        ),
        "vton_condition_command": (
            "make runpod-vton-condition-smoke-inputs "
            f"PERSON_IMAGE={paths.person_image} "
            f"GARMENT_IMAGE={paths.garment_image}"
        ),
        "conditioned_person_image": str(paths.conditioned_person_image),
        "conditioned_garment_image": str(paths.conditioned_garment_image),
        "conditioning_report": str(paths.conditioning_report),
        "leffa_conditioned_smoke_command": (
            "make runpod-leffa-conditioned-smoke "
            f"RUNPOD_LEFFA_GARMENT_TYPE={_leffa_garment_type(garment_category)} "
            f"PERSON_IMAGE={paths.person_image} "
            f"GARMENT_IMAGE={paths.garment_image}"
        ),
        "note": (
            "Smoke inputs are for local pipeline/runtime validation. Use real "
            "kiosk captures and garments for final quality evaluation."
        ),
    }
    paths.manifest.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")

    return {
        "data_dir": str(data_dir),
        "fixture_dir": str(fixture_dir),
        "created": created,
        "person_image": str(paths.person_image),
        "garment_image": str(paths.garment_image),
        "garment_category": garment_category,
        "catvton_cloth_type": garment_category,
        "leffa_garment_type": payload["leffa_garment_type"],
        "manifest": str(paths.manifest),
        "smoke_command": payload["smoke_command"],
        "catvton_smoke_command": payload["catvton_smoke_command"],
        "leffa_smoke_command": payload["leffa_smoke_command"],
        "vton_condition_command": payload["vton_condition_command"],
        "leffa_conditioned_smoke_command": payload["leffa_conditioned_smoke_command"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--session-stem", default=DEFAULT_SESSION_STEM)
    parser.add_argument("--garment-stem", default=DEFAULT_GARMENT_STEM)
    parser.add_argument(
        "--garment-category",
        choices=("upper", "lower", "overall", "inner", "outer"),
        default=DEFAULT_GARMENT_CATEGORY,
        help="Garment category used by VTON-specific smoke tests such as CatVTON",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = prepare_qwen_edit_smoke_data(
        data_dir=args.data_dir,
        fixture_dir=args.fixture_dir,
        session_stem=args.session_stem,
        garment_stem=args.garment_stem,
        garment_category=args.garment_category,
        overwrite=args.overwrite,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _fixture_sources(fixture_dir: Path) -> dict[str, Path]:
    return {
        "person_image": fixture_dir / "front.png",
        "garment_image": fixture_dir / "garment.webp",
    }


def _leffa_garment_type(garment_category: str) -> str:
    if garment_category == "lower":
        return "lower_body"
    if garment_category == "overall":
        return "dresses"
    return "upper_body"


def _create_person_capture(path: Path) -> None:
    image = Image.new("RGB", (1024, 1024), (238, 238, 234))
    draw = ImageDraw.Draw(image)

    # Studio floor and soft backdrop.
    draw.rectangle((0, 760, 1024, 1024), fill=(226, 225, 220))
    draw.ellipse((250, 875, 774, 930), fill=(207, 206, 200))

    # Body silhouette.
    skin = (182, 124, 84)
    shirt = (235, 238, 240)
    shorts = (173, 163, 142)
    shoes = (238, 232, 220)
    hair = (45, 35, 30)

    draw.ellipse((435, 105, 589, 255), fill=skin)
    draw.pieslice((420, 70, 604, 180), start=180, end=360, fill=hair)
    draw.rectangle((475, 238, 549, 295), fill=skin)
    draw.rounded_rectangle((360, 282, 664, 590), radius=44, fill=shirt)

    # Arms.
    draw.rounded_rectangle((305, 300, 365, 650), radius=28, fill=skin)
    draw.rounded_rectangle((659, 300, 719, 650), radius=28, fill=skin)
    draw.ellipse((300, 630, 365, 700), fill=skin)
    draw.ellipse((659, 630, 724, 700), fill=skin)

    # Shorts and legs.
    draw.rounded_rectangle((390, 585, 635, 740), radius=26, fill=shorts)
    draw.rounded_rectangle((405, 725, 480, 905), radius=28, fill=skin)
    draw.rounded_rectangle((544, 725, 619, 905), radius=28, fill=skin)
    draw.ellipse((370, 885, 494, 934), fill=shoes)
    draw.ellipse((530, 885, 654, 934), fill=shoes)

    # Non-identifying blurred face impression.
    draw.ellipse((475, 160, 493, 178), fill=(95, 68, 55))
    draw.ellipse((531, 160, 549, 178), fill=(95, 68, 55))
    draw.arc((482, 190, 542, 222), start=15, end=165, fill=(120, 75, 70), width=4)

    _draw_centered_text(
        draw,
        "synthetic front capture",
        y=955,
        width=1024,
        fill=(120, 120, 120),
    )
    image.save(path)


def _create_garment_image(path: Path) -> None:
    image = Image.new("RGB", (1024, 1024), (245, 245, 242))
    draw = ImageDraw.Draw(image)

    shirt = (18, 94, 72)
    accent = (238, 174, 45)
    trim = (12, 54, 46)

    points = [
        (280, 235),
        (410, 180),
        (475, 245),
        (549, 245),
        (614, 180),
        (744, 235),
        (695, 405),
        (650, 385),
        (670, 820),
        (354, 820),
        (374, 385),
        (329, 405),
    ]
    draw.polygon(points, fill=shirt)
    draw.line(points + [points[0]], fill=trim, width=10)
    draw.polygon([(475, 245), (512, 310), (549, 245)], fill=(245, 245, 242))
    draw.line((475, 245, 512, 310, 549, 245), fill=trim, width=8)

    # Pattern and logo-like non-branded marks.
    for x in range(390, 640, 42):
        draw.line((x, 430, x + 80, 760), fill=(28, 120, 95), width=4)
    draw.rectangle((415, 390, 610, 455), fill=accent)
    _draw_centered_text(draw, "SMOKE", y=402, width=1024, fill=shirt)
    _draw_centered_text(draw, "TRY-ON TEST", y=480, width=1024, fill=accent)
    draw.ellipse((450, 535, 500, 585), fill=accent)
    draw.ellipse((524, 535, 574, 585), fill=accent)
    draw.rectangle((478, 555, 546, 570), fill=accent)

    _draw_centered_text(
        draw,
        "synthetic garment reference",
        y=895,
        width=1024,
        fill=(120, 120, 120),
    )
    image.save(path, format="WEBP", quality=92)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    y: int,
    width: int,
    fill: tuple[int, int, int],
) -> None:
    font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) / 2, y), text, fill=fill, font=font)


if __name__ == "__main__":
    raise SystemExit(main())
