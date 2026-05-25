from pathlib import Path

from PIL import Image

from debug_vto import (
    DebugVTOConfig,
    NoOpPoseControlBlock,
    SegmentationBlock,
    create_geometric_upper_body_mask,
)


def test_geometric_upper_body_mask_targets_torso_without_covering_face():
    person = Image.new("RGB", (100, 100), color=(12, 34, 56))

    mask = create_geometric_upper_body_mask(person)

    assert mask.mode == "L"
    assert mask.size == person.size
    assert mask.getpixel((50, 55)) == 255
    assert mask.getpixel((50, 12)) == 0
    assert mask.getpixel((5, 55)) == 0


def test_segmentation_block_prefers_manual_mask_when_available(tmp_path: Path):
    person = Image.new("RGB", (20, 20), color=(12, 34, 56))
    mask_path = tmp_path / "manual_mask.png"
    Image.new("L", (10, 10), color=255).save(mask_path)
    config = DebugVTOConfig(mask_path=mask_path)

    result = SegmentationBlock(config).run(person)

    assert result.source == "manual"
    assert result.mask.mode == "L"
    assert result.mask.size == person.size


def test_segmentation_block_falls_back_to_geometric_mask():
    person = Image.new("RGB", (100, 100), color=(12, 34, 56))
    config = DebugVTOConfig(mask_path=Path("missing-mask.png"))

    result = SegmentationBlock(config).run(person)

    assert result.source == "geometric-upper-body"
    assert result.mask.getpixel((50, 55)) == 255


def test_pose_control_block_is_explicit_noop_until_densepose_is_integrated():
    person = Image.new("RGB", (20, 20), color=(12, 34, 56))
    mask = Image.new("L", (20, 20), color=255)

    result = NoOpPoseControlBlock().run(person, mask)

    assert result.source == "none"
    assert result.control_image is None
    assert result.notes
