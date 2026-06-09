"""
Smoke test local Qwen Image Edit inference on a GPU machine.

This script intentionally does not integrate with the API or worker. It answers
one question first: can the selected local Qwen image-edit pipeline load and
produce one image on the current GPU/runtime?
"""

from __future__ import annotations

import argparse
import inspect
import json
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_MODEL_ID = "Qwen/Qwen-Image-Edit-2509"
DEFAULT_PROMPT = (
    "Use the first image as the person reference and the second image as the "
    "garment reference. Create a realistic virtual try-on preview where the "
    "person wears the garment. Preserve the person's pose, body proportions, "
    "skin tone, hands, face position, shorts, shoes, and studio background. "
    "Preserve the garment color, logo, text, sleeve length, collar, pattern, "
    "and fabric details as much as possible. Do not add extra accessories."
)
DEFAULT_NEGATIVE_PROMPT = "blurry, low quality, distorted body, extra limbs, bad hands"


def progress(message: str) -> None:
    print(f"[local-qwen-edit] {message}", flush=True)


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
        description="Run one local Qwen image-edit smoke test",
    )
    parser.add_argument(
        "--person-image",
        required=True,
        type=Path,
        help="Person/front capture image path",
    )
    parser.add_argument(
        "--garment-image",
        type=Path,
        help="Optional garment reference image path. Required for edit-plus mode.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output image path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Output report JSON path. Defaults to <output>.json",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Image edit prompt",
    )
    parser.add_argument(
        "--negative-prompt",
        default=DEFAULT_NEGATIVE_PROMPT,
        help="Negative prompt. Use a single space to match Qwen examples.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Hugging Face model id. Default targets multi-image local smoke.",
    )
    parser.add_argument(
        "--pipeline",
        choices=("auto", "edit", "edit-plus"),
        default="auto",
        help="Qwen pipeline class. auto chooses edit-plus when garment image exists.",
    )
    parser.add_argument(
        "--size",
        default="1024x1024",
        help="Requested output size in WIDTHxHEIGHT format when supported",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu", "mps"),
        default="auto",
        help="Torch device. auto prefers CUDA, then MPS, then CPU.",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "bfloat16", "float16", "float32"),
        default="auto",
        help="Torch dtype. auto uses bfloat16 on CUDA, float32 elsewhere.",
    )
    parser.add_argument(
        "--device-map",
        default="none",
        help=(
            "Optional Diffusers device_map passed to from_pretrained. "
            "Use none, cuda, balanced, or auto."
        ),
    )
    parser.add_argument(
        "--cpu-offload",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable model CPU offload after loading when supported",
    )
    parser.add_argument(
        "--steps",
        type=_positive_int,
        default=20,
        help="Diffusion inference steps",
    )
    parser.add_argument(
        "--true-cfg-scale",
        type=float,
        default=4.0,
        help="Qwen classifier-free guidance scale",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args(argv)


def resolve_device(requested_device: str) -> str:
    if requested_device != "auto":
        return requested_device

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def resolve_dtype(requested_dtype: str, *, device: str):
    import torch

    if requested_dtype == "bfloat16":
        return torch.bfloat16
    if requested_dtype == "float16":
        return torch.float16
    if requested_dtype == "float32":
        return torch.float32
    return torch.bfloat16 if device == "cuda" else torch.float32


def validate_device_runtime(device: str) -> None:
    if device != "cuda":
        return

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA was requested but torch.cuda.is_available() is false. "
            "This usually means the RunPod template has an NVIDIA driver / "
            "PyTorch CUDA build mismatch. Fix the pod image or install a torch "
            "build compatible with the installed driver before downloading the "
            "local Qwen image-edit model."
        )

    try:
        device_name = torch.cuda.get_device_name(0)
    except Exception as exc:  # pragma: no cover - driver failure path
        raise RuntimeError(
            "CUDA was requested but the CUDA runtime could not initialize. "
            "Fix the NVIDIA driver / PyTorch CUDA compatibility before "
            "downloading the local Qwen image-edit model."
        ) from exc

    progress(f"cuda runtime ready: {device_name}")


def resolve_pipeline_name(pipeline: str, *, garment_image: Path | None) -> str:
    if pipeline != "auto":
        return pipeline
    return "edit-plus" if garment_image else "edit"


def load_pipeline(
    *,
    model_id: str,
    pipeline_name: str,
    torch_dtype: Any,
    device: str,
    device_map: str,
    cpu_offload: bool,
):
    import torch

    try:
        from diffusers import QwenImageEditPipeline, QwenImageEditPlusPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Your installed diffusers version does not expose Qwen image-edit "
            "pipelines. On the RunPod smoke machine, install a recent diffusers "
            "build before running this script, for example: "
            "pip install -U git+https://github.com/huggingface/diffusers "
            "transformers accelerate safetensors"
        ) from exc

    pipeline_cls = (
        QwenImageEditPlusPipeline
        if pipeline_name == "edit-plus"
        else QwenImageEditPipeline
    )

    progress(f"loading {pipeline_cls.__name__} from {model_id}")
    from_pretrained_kwargs: dict[str, Any] = {}
    if _callable_accepts_kwarg(pipeline_cls.from_pretrained, "torch_dtype"):
        from_pretrained_kwargs["torch_dtype"] = torch_dtype
    elif _callable_accepts_kwarg(pipeline_cls.from_pretrained, "dtype"):
        from_pretrained_kwargs["dtype"] = torch_dtype

    if device_map != "none":
        from_pretrained_kwargs["device_map"] = device_map

    pipeline = pipeline_cls.from_pretrained(model_id, **from_pretrained_kwargs)
    progress("pipeline loaded")

    if device_map == "none":
        if hasattr(pipeline, "to"):
            progress(f"moving pipeline to dtype={torch_dtype}")
            pipeline = pipeline.to(torch_dtype)
            progress(f"moving pipeline to device={device}")
            pipeline = pipeline.to(device)
    elif hasattr(pipeline, "to") and device == "cuda":
        progress(f"using device_map={device_map}; skipping explicit pipeline.to(cuda)")

    if cpu_offload and hasattr(pipeline, "enable_model_cpu_offload"):
        progress("enabling model CPU offload")
        pipeline.enable_model_cpu_offload()
    if hasattr(pipeline, "enable_attention_slicing"):
        pipeline.enable_attention_slicing("auto")
    if hasattr(pipeline, "enable_vae_slicing"):
        pipeline.enable_vae_slicing()
    if hasattr(pipeline, "set_progress_bar_config"):
        pipeline.set_progress_bar_config(disable=False)

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    return pipeline


def generate_smoke(
    *,
    person_image: Path,
    garment_image: Path | None,
    output: Path,
    report: Path,
    prompt: str,
    negative_prompt: str,
    model_id: str,
    pipeline_name: str,
    size: str,
    device: str,
    dtype: str,
    device_map: str,
    cpu_offload: bool,
    steps: int,
    true_cfg_scale: float,
    seed: int,
) -> dict[str, Any]:
    import torch

    started_at = datetime.now(UTC)
    started_monotonic = time.perf_counter()
    resolved_pipeline = resolve_pipeline_name(
        pipeline_name, garment_image=garment_image
    )
    if resolved_pipeline == "edit-plus" and garment_image is None:
        raise ValueError("--garment-image is required for edit-plus pipeline")

    width, height = parse_size(size)
    resolved_device = resolve_device(device)
    validate_device_runtime(resolved_device)
    torch_dtype = resolve_dtype(dtype, device=resolved_device)
    progress(f"using device={resolved_device}, dtype={torch_dtype}")

    pipeline = load_pipeline(
        model_id=model_id,
        pipeline_name=resolved_pipeline,
        torch_dtype=torch_dtype,
        device=resolved_device,
        device_map=device_map,
        cpu_offload=cpu_offload,
    )

    images = [_load_rgb_image(person_image)]
    if garment_image is not None:
        images.append(_load_rgb_image(garment_image))

    generator_device = resolved_device if resolved_device in {"cuda", "cpu"} else "cpu"
    generator = torch.Generator(device=generator_device).manual_seed(seed)

    def step_callback(pipeline, step_index, timestep, callback_kwargs):
        progress(f"step {step_index + 1}/{steps}")
        return callback_kwargs

    pipeline_kwargs: dict[str, Any] = {
        "image": images if resolved_pipeline == "edit-plus" else images[0],
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "num_inference_steps": steps,
        "true_cfg_scale": true_cfg_scale,
        "generator": generator,
    }
    if _pipeline_accepts_kwarg(pipeline, "width"):
        pipeline_kwargs["width"] = width
    if _pipeline_accepts_kwarg(pipeline, "height"):
        pipeline_kwargs["height"] = height
    if _pipeline_accepts_kwarg(pipeline, "callback_on_step_end"):
        pipeline_kwargs["callback_on_step_end"] = step_callback
    if _pipeline_accepts_kwarg(pipeline, "callback_on_step_end_tensor_inputs"):
        pipeline_kwargs["callback_on_step_end_tensor_inputs"] = []

    progress("generating image")
    with torch.inference_mode():
        result = pipeline(**pipeline_kwargs)

    output.parent.mkdir(parents=True, exist_ok=True)
    result.images[0].save(output)
    progress(f"saved {output}")

    finished_at = datetime.now(UTC)
    report_payload: dict[str, Any] = {
        "success": True,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "generation_time_seconds": time.perf_counter() - started_monotonic,
        "model_id": model_id,
        "pipeline": resolved_pipeline,
        "device": resolved_device,
        "dtype": str(torch_dtype).replace("torch.", ""),
        "device_map": device_map,
        "cpu_offload": cpu_offload,
        "steps": steps,
        "true_cfg_scale": true_cfg_scale,
        "seed": seed,
        "size": size,
        "person_image": str(person_image),
        "garment_image": str(garment_image) if garment_image else None,
        "output": str(output),
        "report": str(report),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "runtime": collect_runtime_metrics(resolved_device),
        "error": None,
    }
    _write_report(report, report_payload)
    return report_payload


def collect_runtime_metrics(device: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    try:
        import psutil

        virtual_memory = psutil.virtual_memory()
        metrics["system_memory_total_gb"] = round(
            virtual_memory.total / 1024**3,
            3,
        )
        metrics["system_memory_available_gb"] = round(
            virtual_memory.available / 1024**3,
            3,
        )
    except Exception as exc:  # pragma: no cover - best-effort telemetry
        metrics["system_memory_error"] = str(exc)

    if device == "cuda":
        try:
            import torch

            current_device = torch.cuda.current_device()
            properties = torch.cuda.get_device_properties(current_device)
            metrics["cuda_device_name"] = properties.name
            metrics["cuda_total_vram_gb"] = round(
                properties.total_memory / 1024**3,
                3,
            )
            metrics["cuda_peak_allocated_gb"] = round(
                torch.cuda.max_memory_allocated(current_device) / 1024**3,
                3,
            )
            metrics["cuda_peak_reserved_gb"] = round(
                torch.cuda.max_memory_reserved(current_device) / 1024**3,
                3,
            )
        except Exception as exc:  # pragma: no cover - best-effort telemetry
            metrics["cuda_error"] = str(exc)

    return metrics


def _load_rgb_image(path: Path) -> Image.Image:
    if not path.exists():
        raise FileNotFoundError(f"Input image not found: {path}")
    return Image.open(path).convert("RGB")


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    progress(f"wrote report {path}")


def _pipeline_accepts_kwarg(pipeline: Any, kwarg: str) -> bool:
    try:
        signature = inspect.signature(pipeline.__call__)
    except (TypeError, ValueError):
        return False
    return kwarg in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def _callable_accepts_kwarg(callable_obj: Any, kwarg: str) -> bool:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return True
    return kwarg in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_path = args.report or args.output.with_suffix(f"{args.output.suffix}.json")
    try:
        generate_smoke(
            person_image=args.person_image,
            garment_image=args.garment_image,
            output=args.output,
            report=report_path,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            model_id=args.model_id,
            pipeline_name=args.pipeline,
            size=args.size,
            device=args.device,
            dtype=args.dtype,
            device_map=args.device_map,
            cpu_offload=args.cpu_offload,
            steps=args.steps,
            true_cfg_scale=args.true_cfg_scale,
            seed=args.seed,
        )
        return 0
    except Exception as exc:
        failed_payload = {
            "success": False,
            "finished_at": datetime.now(UTC).isoformat(),
            "model_id": args.model_id,
            "pipeline": args.pipeline,
            "device": args.device,
            "dtype": args.dtype,
            "device_map": args.device_map,
            "cpu_offload": args.cpu_offload,
            "steps": args.steps,
            "true_cfg_scale": args.true_cfg_scale,
            "seed": args.seed,
            "size": args.size,
            "person_image": str(args.person_image),
            "garment_image": str(args.garment_image) if args.garment_image else None,
            "output": str(args.output),
            "report": str(report_path),
            "prompt": args.prompt,
            "negative_prompt": args.negative_prompt,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        }
        _write_report(report_path, failed_payload)
        progress(f"failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
