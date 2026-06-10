"""
Smoke test CatVTON local inference on a GPU machine.

This script intentionally stays outside the API/worker path. It answers one
question first: can a cloned CatVTON repo load and produce one image on the
current RunPod runtime?
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

from scripts.local_qwen_edit_smoke import collect_runtime_metrics
from scripts.local_qwen_edit_smoke import parse_size


DEFAULT_REPO_URL = "https://github.com/Zheng-Chong/CatVTON.git"
DEFAULT_BASE_MODEL_PATH = "runwayml/stable-diffusion-inpainting"
DEFAULT_RESUME_PATH = "zhengchong/CatVTON"


def progress(message: str) -> None:
    print(f"[local-catvton] {message}", flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one local CatVTON smoke test",
    )
    parser.add_argument(
        "--person-image",
        required=True,
        type=Path,
        help="Person/front capture image path",
    )
    parser.add_argument(
        "--garment-image",
        required=True,
        type=Path,
        help="Garment reference image path",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output PNG path")
    parser.add_argument(
        "--report",
        type=Path,
        help="Output report JSON path. Defaults to <output>.json",
    )
    parser.add_argument(
        "--catvton-root",
        type=Path,
        required=True,
        help="Local CatVTON repo path. The script clones it when missing.",
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help="CatVTON git repository URL",
    )
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Do not clone CatVTON when --catvton-root is missing",
    )
    parser.add_argument(
        "--base-model-path",
        default=DEFAULT_BASE_MODEL_PATH,
        help="Base inpainting model path or Hugging Face model id",
    )
    parser.add_argument(
        "--resume-path",
        default=DEFAULT_RESUME_PATH,
        help="CatVTON checkpoint path or Hugging Face model id",
    )
    parser.add_argument(
        "--size",
        default="768x1024",
        help="Requested CatVTON size in WIDTHxHEIGHT format",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Torch device. auto prefers CUDA.",
    )
    parser.add_argument(
        "--mixed-precision",
        choices=("no", "fp16", "bf16"),
        default="bf16",
        help="CatVTON precision mode",
    )
    parser.add_argument(
        "--cloth-type",
        choices=("upper", "lower", "overall", "inner", "outer"),
        default="upper",
        help="Garment/body region for CatVTON mask generation",
    )
    parser.add_argument(
        "--mask-mode",
        choices=("auto", "rough", "provided"),
        default="auto",
        help=(
            "auto uses CatVTON DensePose/SCHP AutoMasker; rough uses a simple "
            "synthetic mask for runtime smoke; provided requires --mask-image."
        ),
    )
    parser.add_argument(
        "--mask-image",
        type=Path,
        help="Optional mask image path when --mask-mode=provided",
    )
    parser.add_argument(
        "--steps",
        type=_positive_int,
        default=30,
        help="Diffusion inference steps",
    )
    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=2.5,
        help="CatVTON classifier-free guidance scale",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--allow-tf32",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow TF32 on compatible NVIDIA GPUs",
    )
    parser.add_argument(
        "--skip-safety-check",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip Stable Diffusion safety checker for smoke speed/stability",
    )
    parser.add_argument(
        "--check-imports-only",
        action="store_true",
        help="Clone/use CatVTON and validate imports, then exit before loading models",
    )
    return parser.parse_args(argv)


def _positive_int(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed_value


def resolve_device(requested_device: str) -> str:
    if requested_device != "auto":
        return requested_device

    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def validate_device_runtime(device: str) -> None:
    if device != "cuda":
        return

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA was requested but torch.cuda.is_available() is false. "
            "Fix the RunPod image or PyTorch CUDA wheel before running CatVTON."
        )

    try:
        device_name = torch.cuda.get_device_name(0)
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "CUDA was requested but the CUDA runtime could not initialize. "
            f"Original CUDA error: {exc!r}"
        ) from exc

    progress(f"cuda runtime ready: {device_name}")


def resolve_weight_dtype(mixed_precision: str):
    import torch

    return {
        "no": torch.float32,
        "fp16": torch.float16,
        "bf16": torch.bfloat16,
    }[mixed_precision]


def ensure_catvton_repo(
    *,
    catvton_root: Path,
    repo_url: str,
    no_clone: bool,
) -> None:
    if (catvton_root / "model" / "pipeline.py").exists():
        progress(f"using CatVTON repo at {catvton_root}")
        return

    if no_clone:
        raise FileNotFoundError(
            f"CatVTON repo not found at {catvton_root}. "
            "Remove --no-clone or clone the repo manually."
        )

    catvton_root.parent.mkdir(parents=True, exist_ok=True)
    progress(f"cloning CatVTON from {repo_url} to {catvton_root}")
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(catvton_root)],
        check=True,
    )


def load_catvton_modules(catvton_root: Path, *, include_automasker: bool = True):
    root = str(catvton_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from diffusers.image_processor import VaeImageProcessor
        from huggingface_hub import snapshot_download
        from model.pipeline import CatVTONPipeline
        from utils import init_weight_dtype
        from utils import resize_and_crop
        from utils import resize_and_padding
    except ImportError as exc:
        raise RuntimeError(
            "CatVTON core dependencies are missing or incompatible. Run "
            "`make runpod-install-catvton-deps`, then retry the smoke. "
            f"Original import error: {type(exc).__name__}: {exc}"
        ) from exc

    modules = {
        "CatVTONPipeline": CatVTONPipeline,
        "VaeImageProcessor": VaeImageProcessor,
        "init_weight_dtype": init_weight_dtype,
        "resize_and_crop": resize_and_crop,
        "resize_and_padding": resize_and_padding,
        "snapshot_download": snapshot_download,
    }

    if include_automasker:
        try:
            from model.cloth_masker import AutoMasker
        except ImportError as exc:
            raise RuntimeError(
                "CatVTON AutoMasker dependencies are missing or incompatible. "
                "Use `make runpod-catvton-smoke RUNPOD_CATVTON_MASK_MODE=rough` "
                "to smoke the core pipeline first, or install the DensePose/SCHP "
                "dependencies needed by CatVTON auto masking. "
                f"Original import error: {type(exc).__name__}: {exc}"
            ) from exc
        modules["AutoMasker"] = AutoMasker

    return modules


def generate_smoke(
    *,
    person_image: Path,
    garment_image: Path,
    output: Path,
    report: Path,
    catvton_root: Path,
    repo_url: str,
    no_clone: bool,
    base_model_path: str,
    resume_path: str,
    size: str,
    device: str,
    mixed_precision: str,
    cloth_type: str,
    mask_mode: str,
    mask_image: Path | None,
    steps: int,
    guidance_scale: float,
    seed: int,
    allow_tf32: bool,
    skip_safety_check: bool,
    check_imports_only: bool = False,
) -> dict[str, Any]:
    import torch

    started_at = datetime.now(UTC)
    started_monotonic = time.perf_counter()
    width, height = parse_size(size)
    resolved_device = resolve_device(device)
    validate_device_runtime(resolved_device)
    ensure_catvton_repo(
        catvton_root=catvton_root,
        repo_url=repo_url,
        no_clone=no_clone,
    )
    modules = load_catvton_modules(
        catvton_root,
        include_automasker=mask_mode == "auto",
    )
    if check_imports_only:
        progress("CatVTON imports passed")
        report_payload: dict[str, Any] = {
            "success": True,
            "finished_at": datetime.now(UTC).isoformat(),
            "model": "CatVTON",
            "repo_url": repo_url,
            "catvton_root": str(catvton_root),
            "check_imports_only": True,
            "error": None,
        }
        _write_report(report, report_payload)
        return report_payload

    ensure_input_exists(person_image, "person image")
    ensure_input_exists(garment_image, "garment image")
    if mask_mode == "provided":
        if mask_image is None:
            raise ValueError("--mask-image is required when --mask-mode=provided")
        ensure_input_exists(mask_image, "mask image")

    snapshot_download = modules["snapshot_download"]
    resume_candidate = Path(resume_path).expanduser()
    repo_path = (
        str(resume_candidate)
        if resume_candidate.exists()
        else snapshot_download(repo_id=resume_path)
    )
    progress(f"using CatVTON checkpoint at {repo_path}")

    weight_dtype = resolve_weight_dtype(mixed_precision)
    progress(
        "loading CatVTON pipeline "
        f"(base={base_model_path}, dtype={weight_dtype}, device={resolved_device})"
    )
    pipeline = modules["CatVTONPipeline"](
        base_ckpt=base_model_path,
        attn_ckpt=repo_path,
        attn_ckpt_version="mix",
        weight_dtype=weight_dtype,
        use_tf32=allow_tf32,
        device=resolved_device,
        skip_safety_check=skip_safety_check,
    )

    person = _load_rgb_image(person_image)
    garment = _load_rgb_image(garment_image)
    target_size = (width, height)
    person = modules["resize_and_crop"](person, target_size)
    garment = modules["resize_and_padding"](garment, target_size)

    mask = build_mask(
        modules=modules,
        person=person,
        mask_mode=mask_mode,
        mask_image=mask_image,
        cloth_type=cloth_type,
        target_size=target_size,
        checkpoint_root=Path(repo_path),
        device=resolved_device,
    )

    generator_device = resolved_device if resolved_device in {"cuda", "cpu"} else "cpu"
    generator = torch.Generator(device=generator_device).manual_seed(seed)

    if resolved_device == "cuda":
        try:
            torch.cuda.reset_peak_memory_stats()
        except Exception as exc:  # pragma: no cover - environment-specific
            progress(f"skipping cuda peak memory reset: {exc!r}")

    progress("generating image")
    with torch.inference_mode():
        result_images = pipeline(
            image=person,
            condition_image=garment,
            mask=mask,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=generator,
            height=height,
            width=width,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    result_images[0].save(output)
    progress(f"saved {output}")

    finished_at = datetime.now(UTC)
    report_payload: dict[str, Any] = {
        "success": True,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "generation_time_seconds": time.perf_counter() - started_monotonic,
        "model": "CatVTON",
        "repo_url": repo_url,
        "catvton_root": str(catvton_root),
        "base_model_path": base_model_path,
        "resume_path": resume_path,
        "checkpoint_path": str(repo_path),
        "device": resolved_device,
        "mixed_precision": mixed_precision,
        "size": size,
        "width": width,
        "height": height,
        "cloth_type": cloth_type,
        "mask_mode": mask_mode,
        "mask_image": str(mask_image) if mask_image else None,
        "steps": steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "allow_tf32": allow_tf32,
        "skip_safety_check": skip_safety_check,
        "person_image": str(person_image),
        "garment_image": str(garment_image),
        "output": str(output),
        "report": str(report),
        "runtime": collect_runtime_metrics(resolved_device),
        "error": None,
    }
    _write_report(report, report_payload)
    return report_payload


def build_mask(
    *,
    modules: dict[str, Any],
    person: Image.Image,
    mask_mode: str,
    mask_image: Path | None,
    cloth_type: str,
    target_size: tuple[int, int],
    checkpoint_root: Path,
    device: str,
) -> Image.Image:
    if mask_mode == "provided":
        assert mask_image is not None
        mask = _load_mask_image(mask_image)
        mask = modules["resize_and_crop"](mask, target_size)
    elif mask_mode == "rough":
        progress("using rough synthetic mask for runtime smoke")
        mask = create_rough_mask(target_size, cloth_type=cloth_type)
    else:
        progress("building mask with CatVTON AutoMasker")
        automasker = modules["AutoMasker"](
            densepose_ckpt=str(checkpoint_root / "DensePose"),
            schp_ckpt=str(checkpoint_root / "SCHP"),
            device=device,
        )
        mask = automasker(person, cloth_type)["mask"]

    mask_processor = modules["VaeImageProcessor"](
        vae_scale_factor=8,
        do_normalize=False,
        do_binarize=True,
        do_convert_grayscale=True,
    )
    return mask_processor.blur(mask, blur_factor=9)


def create_rough_mask(size: tuple[int, int], *, cloth_type: str) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)

    if cloth_type in {"lower"}:
        box = (
            round(width * 0.22),
            round(height * 0.45),
            round(width * 0.78),
            round(height * 0.96),
        )
    elif cloth_type in {"overall"}:
        box = (
            round(width * 0.16),
            round(height * 0.16),
            round(width * 0.84),
            round(height * 0.96),
        )
    else:
        box = (
            round(width * 0.14),
            round(height * 0.16),
            round(width * 0.86),
            round(height * 0.68),
        )

    from PIL import ImageDraw

    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(box, radius=max(4, width // 30), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(3, width // 100)))


def ensure_input_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def _load_rgb_image(path: Path) -> Image.Image:
    ensure_input_exists(path, "input image")
    with Image.open(path) as image:
        return image.convert("RGB")


def _load_mask_image(path: Path) -> Image.Image:
    ensure_input_exists(path, "mask image")
    with Image.open(path) as image:
        return image.convert("L")


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    progress(f"wrote report {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_path = args.report or args.output.with_suffix(f"{args.output.suffix}.json")
    try:
        generate_smoke(
            person_image=args.person_image,
            garment_image=args.garment_image,
            output=args.output,
            report=report_path,
            catvton_root=args.catvton_root,
            repo_url=args.repo_url,
            no_clone=args.no_clone,
            base_model_path=args.base_model_path,
            resume_path=args.resume_path,
            size=args.size,
            device=args.device,
            mixed_precision=args.mixed_precision,
            cloth_type=args.cloth_type,
            mask_mode=args.mask_mode,
            mask_image=args.mask_image,
            steps=args.steps,
            guidance_scale=args.guidance_scale,
            seed=args.seed,
            allow_tf32=args.allow_tf32,
            skip_safety_check=args.skip_safety_check,
            check_imports_only=args.check_imports_only,
        )
        return 0
    except Exception as exc:
        failed_payload = {
            "success": False,
            "finished_at": datetime.now(UTC).isoformat(),
            "model": "CatVTON",
            "repo_url": args.repo_url,
            "catvton_root": str(args.catvton_root),
            "base_model_path": args.base_model_path,
            "resume_path": args.resume_path,
            "device": args.device,
            "mixed_precision": args.mixed_precision,
            "size": args.size,
            "cloth_type": args.cloth_type,
            "mask_mode": args.mask_mode,
            "mask_image": str(args.mask_image) if args.mask_image else None,
            "steps": args.steps,
            "guidance_scale": args.guidance_scale,
            "seed": args.seed,
            "allow_tf32": args.allow_tf32,
            "skip_safety_check": args.skip_safety_check,
            "check_imports_only": args.check_imports_only,
            "person_image": str(args.person_image),
            "garment_image": str(args.garment_image),
            "output": str(args.output),
            "report": str(report_path),
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
