from unittest.mock import Mock

from PIL import Image

import scripts.local_avatar_generate as local_avatar_generate


def test_parse_args_supports_local_avatar_generation_options(tmp_path):
    output_path = tmp_path / "avatar.png"

    args = local_avatar_generate.parse_args(
        [
            "--prompt",
            "synthetic avatar",
            "--output",
            str(output_path),
            "--size",
            "768x1024",
            "--model-id",
            "stabilityai/sdxl-turbo",
            "--device",
            "cpu",
            "--steps",
            "3",
            "--guidance-scale",
            "0.0",
            "--seed",
            "7",
            "--no-compact-avatar-prompt",
        ]
    )

    assert args.prompt == "synthetic avatar"
    assert args.output == output_path
    assert args.size == "768x1024"
    assert args.model_id == "stabilityai/sdxl-turbo"
    assert args.device == "cpu"
    assert args.steps == 3
    assert args.guidance_scale == 0.0
    assert args.seed == 7
    assert args.compact_avatar_prompt is False


def test_parse_size_returns_width_and_height():
    assert local_avatar_generate.parse_size("768x1024") == (768, 1024)


def test_parse_size_rejects_invalid_size():
    try:
        local_avatar_generate.parse_size("1024")
    except ValueError as exc:
        assert "Expected size format" in str(exc)
    else:
        raise AssertionError("parse_size should reject invalid size")


def test_generate_image_saves_pipeline_output(tmp_path, monkeypatch):
    output_path = tmp_path / "avatar.png"
    pipeline = Mock()
    pipeline.return_value.images = [Image.new("RGB", (16, 16), color="white")]
    pipeline.to.return_value = pipeline
    pipeline.enable_attention_slicing = Mock()
    pipeline.enable_vae_slicing = Mock()

    monkeypatch.setattr(
        local_avatar_generate,
        "load_pipeline",
        Mock(return_value=pipeline),
    )
    monkeypatch.setattr(local_avatar_generate, "resolve_device", Mock(return_value="cpu"))

    local_avatar_generate.generate_image(
        prompt="synthetic avatar",
        output=output_path,
        size="16x16",
        model_id="stabilityai/sdxl-turbo",
        device="auto",
        steps=2,
        guidance_scale=0.0,
        seed=42,
        compact_prompt=False,
    )

    assert output_path.exists()
    pipeline.assert_called_once()
    call_kwargs = pipeline.call_args.kwargs
    assert call_kwargs["prompt"] == "synthetic avatar"
    assert "negative_prompt" in call_kwargs
    assert "callback_on_step_end" in call_kwargs
    assert call_kwargs["width"] == 16
    assert call_kwargs["height"] == 16
    assert call_kwargs["num_inference_steps"] == 2
    assert call_kwargs["guidance_scale"] == 0.0


def test_generate_image_prints_progress_messages(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "avatar.png"
    pipeline = Mock()
    pipeline.return_value.images = [Image.new("RGB", (16, 16), color="white")]
    pipeline.to.return_value = pipeline
    pipeline.enable_attention_slicing = Mock()
    pipeline.enable_vae_slicing = Mock()

    monkeypatch.setattr(
        local_avatar_generate,
        "load_pipeline",
        Mock(return_value=pipeline),
    )
    monkeypatch.setattr(local_avatar_generate, "resolve_device", Mock(return_value="cpu"))

    local_avatar_generate.generate_image(
        prompt="synthetic avatar",
        output=output_path,
        size="16x16",
        model_id="stabilityai/sdxl-turbo",
        device="auto",
        steps=2,
        guidance_scale=0.0,
        seed=42,
        compact_prompt=False,
    )

    output = capsys.readouterr().out
    assert "[local-avatar] resolving device" in output
    assert "[local-avatar] loading model stabilityai/sdxl-turbo" in output
    assert "[local-avatar] generating image" in output
    assert f"[local-avatar] saved {output_path}" in output


def test_compact_avatar_prompt_preserves_body_and_framing_cues():
    prompt = (
        "Create a photorealistic synthetic human model of an adult male person "
        "with tall height range, athletic build, and broad shoulders. Use tan "
        "skin tone. The face must be softly blurred and non-identifying. "
        "Use simple plain fitted base clothing with no graphics: a plain neutral "
        "short-sleeve fitted t-shirt with bare forearms visible and plain neutral "
        "shorts. Frame the avatar as a full-body photo from head to shoes with "
        "legs fully visible and feet fully visible."
    )

    compact = local_avatar_generate.compact_avatar_prompt(prompt)

    assert len(compact.split()) <= 70
    assert "adult male" in compact
    assert "tall athletic build" in compact
    assert "broad shoulders" in compact
    assert "tan skin" in compact
    assert "short-sleeve" in compact
    assert "full-body" in compact
    assert "blurred non-identifying face" in compact
