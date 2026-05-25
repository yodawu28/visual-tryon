import base64
import io

from PIL import Image

from run_vto import (
    build_arg_parser,
    create_auto_mask,
    load_rgb_image_from_base64,
    resize_for_pipeline,
)


def _build_base64_image(width: int = 12, height: int = 8) -> str:
    image = Image.new("RGB", (width, height), color=(12, 34, 56))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def test_cli_accepts_file_path_inputs():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--person",
            "person_anonymized.png",
            "--mask",
            "mask_vton.png",
            "--garment",
            "shirt.png",
            "--prompt",
            "Use IMAGE 1 as base...",
        ]
    )

    assert args.person == "person_anonymized.png"
    assert args.mask == "mask_vton.png"
    assert args.garment == "shirt.png"
    assert args.prompt == "Use IMAGE 1 as base..."
    assert args.num_inference_steps == 30
    assert args.guidance_scale == 7.5
    assert (
        args.negative_prompt
        == "deformed, bad anatomy, blurry, naked, NSFW, low quality"
    )
    assert args.disable_safety_checker is True


def test_cli_accepts_base64_inputs_with_auto_mask_full():
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--person-base64",
            "person-b64",
            "--garment-base64",
            "garment-b64",
            "--auto-mask",
            "full",
        ]
    )

    assert args.person_base64 == "person-b64"
    assert args.garment_base64 == "garment-b64"
    assert args.auto_mask == "full"
    assert args.mask is None
    assert args.mask_base64 is None


def test_load_rgb_image_from_base64_accepts_data_url():
    raw_b64 = _build_base64_image()
    data_url = f"data:image/png;base64,{raw_b64}"

    image = load_rgb_image_from_base64(data_url, field_name="person")

    assert image.mode == "RGB"
    assert image.size == (12, 8)


def test_resize_for_pipeline_returns_512_square():
    image = Image.new("RGB", (120, 80), color=(12, 34, 56))

    resized = resize_for_pipeline(image)

    assert resized.size == (512, 512)


def test_create_auto_mask_full_is_white_image():
    person = Image.new("RGB", (20, 10), color=(12, 34, 56))

    mask = create_auto_mask(person, mode="full")

    assert mask.mode == "L"
    assert mask.size == person.size
    assert mask.getbbox() == (0, 0, 20, 10)
    assert mask.getpixel((0, 0)) == 255


def test_create_auto_mask_upper_body_targets_center_torso():
    person = Image.new("RGB", (100, 100), color=(12, 34, 56))

    mask = create_auto_mask(person, mode="upper-body")

    assert mask.mode == "L"
    assert mask.size == person.size
    assert mask.getpixel((50, 55)) == 255
    assert mask.getpixel((5, 5)) == 0
    assert mask.getpixel((50, 95)) == 0
