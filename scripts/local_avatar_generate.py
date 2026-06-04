"""
Generate a synthetic avatar image with a local Diffusers text-to-image model.

This script is intended for LOCAL_AVATAR_COMMAND. It writes one image to the
path provided by --output.
"""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path


DEFAULT_MODEL_ID = "stabilityai/sdxl-turbo"
DEFAULT_NEGATIVE_PROMPT = (
    "cartoon, illustration, sketch, mannequin, plastic skin, logo, text, "
    "watermark, brand mark, accessories, recognizable face, extra limbs, bad hands"
)


def progress(message: str) -> None:
    print(f"[local-avatar] {message}", flush=True)


def parse_size(value: str) -> tuple[int, int]:
    try:
        raw_width, raw_height = value.lower().split("x", maxsplit=1)
        width = int(raw_width)
        height = int(raw_height)
    except ValueError as exc:
        raise ValueError(
            "Expected size format WIDTHxHEIGHT, for example 1024x1024"
        ) from exc

    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be positive")
    return width, height


def _positive_int(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed_value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one local synthetic avatar image",
    )
    parser.add_argument("--prompt", required=True, help="Avatar generation prompt")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output image path written by this script",
    )
    parser.add_argument(
        "--size",
        default="1024x1024",
        help="Output image size in WIDTHxHEIGHT format",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Diffusers model id. Default is a practical MacBook baseline.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "mps", "cuda"),
        default="auto",
        help="Torch device. auto prefers mps on Mac, then cuda, then cpu.",
    )
    parser.add_argument(
        "--steps",
        type=_positive_int,
        default=4,
        help="Diffusion inference steps",
    )
    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=0.0,
        help="Classifier-free guidance scale",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--negative-prompt",
        default=DEFAULT_NEGATIVE_PROMPT,
        help="Short negative prompt used by local Diffusers models",
    )
    parser.add_argument(
        "--compact-avatar-prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compact long API avatar prompts to fit CLIP-style local prompt limits",
    )
    return parser.parse_args(argv)


def resolve_device(requested_device: str) -> str:
    if requested_device != "auto":
        return requested_device

    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_pipeline(*, model_id: str, device: str):
    import torch
    from diffusers import AutoPipelineForText2Image

    progress(f"loading model {model_id}")
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    pipeline = AutoPipelineForText2Image.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    )
    progress(f"moving pipeline to {device}")
    pipeline = pipeline.to(device)

    if hasattr(pipeline, "enable_attention_slicing"):
        pipeline.enable_attention_slicing("auto")
    if hasattr(pipeline, "enable_vae_slicing"):
        pipeline.enable_vae_slicing()

    return pipeline


def compact_avatar_prompt(prompt: str) -> str:
    prompt_lower = prompt.lower()
    gender = _first_match(
        prompt_lower,
        [
            ("adult female", "adult female"),
            ("female person", "adult female"),
            ("adult male", "adult male"),
            ("male person", "adult male"),
            ("neutral", "androgynous adult"),
        ],
        default="adult person",
    )
    height = _first_match(
        prompt_lower,
        [("tall height", "tall"), ("short height", "short")],
        default="average-height",
    )
    build = _first_match(
        prompt_lower,
        [
            ("athletic build", "athletic build"),
            ("slim build", "slim build"),
            ("plus build", "plus-size build"),
        ],
        default="average build",
    )
    shoulders = _first_match(
        prompt_lower,
        [
            ("broad shoulders", "broad shoulders"),
            ("narrow shoulders", "narrow shoulders"),
        ],
        default="natural shoulders",
    )
    skin = _first_match(
        prompt_lower,
        [
            ("light skin", "light skin"),
            ("medium skin", "medium skin"),
            ("tan skin", "tan skin"),
            ("dark skin", "dark skin"),
        ],
        default="natural skin",
    )
    framing = (
        "full-body head-to-shoes photo, legs and feet visible"
        if "full-body" in prompt_lower or "head to shoes" in prompt_lower
        else "upper-body portrait photo"
    )
    top = _first_match(
        prompt_lower,
        [
            ("sleeveless", "plain sleeveless neutral top"),
            ("long-sleeve", "plain long-sleeve neutral top"),
            ("long sleeve", "plain long-sleeve neutral top"),
            ("short-sleeve", "plain short-sleeve neutral t-shirt"),
            ("short sleeve", "plain short-sleeve neutral t-shirt"),
        ],
        default="plain neutral base clothing",
    )
    bottom = "neutral shorts" if "shorts" in prompt_lower else "neutral lower garment"
    return (
        f"photorealistic synthetic {gender}, {height} {build}, {shoulders}, "
        f"{skin}, neutral studio background, front relaxed pose, {top}, {bottom}, "
        f"{framing}, realistic skin texture, blurred non-identifying face"
    )


def _first_match(
    haystack: str,
    candidates: list[tuple[str, str]],
    *,
    default: str,
) -> str:
    for needle, value in candidates:
        if needle in haystack:
            return value
    return default


def _pipeline_accepts_kwarg(pipeline, kwarg: str) -> bool:
    try:
        signature = inspect.signature(pipeline.__call__)
    except (TypeError, ValueError):
        return False
    return kwarg in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def generate_image(
    *,
    prompt: str,
    output: Path,
    size: str,
    model_id: str,
    device: str,
    steps: int,
    guidance_scale: float,
    seed: int,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    compact_prompt: bool = True,
) -> None:
    import torch

    width, height = parse_size(size)
    progress("resolving device")
    resolved_device = resolve_device(device)
    progress(f"using device {resolved_device}")
    progress(f"loading model {model_id}")
    pipeline = load_pipeline(model_id=model_id, device=resolved_device)
    generator_device = resolved_device if resolved_device in {"cuda", "cpu"} else "cpu"
    generator = torch.Generator(device=generator_device).manual_seed(seed)
    effective_prompt = compact_avatar_prompt(prompt) if compact_prompt else prompt
    if effective_prompt != prompt:
        progress(f"compacted prompt: {effective_prompt}")

    def step_callback(pipeline, step_index, timestep, callback_kwargs):
        progress(f"step {step_index + 1}/{steps}")
        return callback_kwargs

    progress("generating image")
    pipeline_kwargs = {
        "prompt": effective_prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance_scale,
        "generator": generator,
        "negative_prompt": negative_prompt,
    }
    if _pipeline_accepts_kwarg(pipeline, "callback_on_step_end"):
        pipeline_kwargs["callback_on_step_end"] = step_callback
    if _pipeline_accepts_kwarg(pipeline, "callback_on_step_end_tensor_inputs"):
        pipeline_kwargs["callback_on_step_end_tensor_inputs"] = []

    result = pipeline(
        **pipeline_kwargs,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    result.images[0].save(output)
    progress(f"saved {output}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generate_image(
        prompt=args.prompt,
        output=args.output,
        size=args.size,
        model_id=args.model_id,
        device=args.device,
        steps=args.steps,
        guidance_scale=args.guidance_scale,
        seed=args.seed,
        negative_prompt=args.negative_prompt,
        compact_prompt=args.compact_avatar_prompt,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
