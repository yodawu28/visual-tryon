"""
Small debug pipeline blocks for local VTO troubleshooting.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class DebugVTOConfig:
    mask_path: Path | None = None


@dataclass(frozen=True)
class SegmentationResult:
    source: str
    mask: Image.Image


@dataclass(frozen=True)
class PoseControlResult:
    source: str
    control_image: Image.Image | None
    notes: str


def create_geometric_upper_body_mask(person: Image.Image) -> Image.Image:
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


class SegmentationBlock:
    def __init__(self, config: DebugVTOConfig):
        self.config = config

    def run(self, person: Image.Image) -> SegmentationResult:
        if self.config.mask_path and self.config.mask_path.exists():
            with Image.open(self.config.mask_path) as mask_image:
                mask = mask_image.convert("L").resize(
                    person.size,
                    Image.Resampling.NEAREST,
                )
            return SegmentationResult(source="manual", mask=mask)

        return SegmentationResult(
            source="geometric-upper-body",
            mask=create_geometric_upper_body_mask(person),
        )


class NoOpPoseControlBlock:
    def run(self, person: Image.Image, mask: Image.Image) -> PoseControlResult:
        return PoseControlResult(
            source="none",
            control_image=None,
            notes="DensePose/control image is not integrated in the debug path.",
        )
