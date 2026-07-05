"""
Smoke test Leffa local inference on a GPU machine.

This script intentionally stays outside the API/worker path. It answers one
question first: can a cloned Leffa repo load and produce one virtual try-on
image on the current RunPod runtime?
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

import numpy as np
from PIL import Image

from scripts.local_qwen_edit_smoke import collect_runtime_metrics
from scripts.local_qwen_edit_smoke import parse_size


DEFAULT_REPO_URL = "https://github.com/franciszzj/Leffa.git"
DEFAULT_MODEL_REPO_ID = "franciszzj/Leffa"
DEFAULT_BASE_MODEL_PATH = "stable-diffusion-inpainting"
DEFAULT_VIRTUAL_TRYON_MODEL = "virtual_tryon.pth"
DEFAULT_VIRTUAL_TRYON_DC_MODEL = "virtual_tryon_dc.pth"


def progress(message: str) -> None:
    print(f"[local-leffa] {message}", flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one local Leffa smoke test")
    parser.add_argument(
        "--person-image",
        type=Path,
        help="Person/front capture image path",
    )
    parser.add_argument(
        "--garment-image",
        type=Path,
        help="Garment reference image path",
    )
    parser.add_argument("--output", type=Path, help="Output PNG path")
    parser.add_argument(
        "--report",
        type=Path,
        help="Output report JSON path. Defaults to <output>.json",
    )
    parser.add_argument(
        "--leffa-root",
        type=Path,
        required=True,
        help="Local Leffa repo path. The script clones it when missing.",
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help="Leffa git repository URL",
    )
    parser.add_argument(
        "--no-clone",
        action="store_true",
        help="Do not clone Leffa when --leffa-root is missing",
    )
    parser.add_argument(
        "--model-repo-id",
        default=DEFAULT_MODEL_REPO_ID,
        help="Hugging Face repo id containing Leffa checkpoints",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        help="Local checkpoint directory. Defaults to <leffa-root>/ckpts.",
    )
    parser.add_argument(
        "--size",
        default="768x1024",
        help="Requested Leffa size in WIDTHxHEIGHT format",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Torch device. auto prefers CUDA.",
    )
    parser.add_argument(
        "--dtype",
        choices=("float16", "float32"),
        default="float16",
        help="Leffa model dtype",
    )
    parser.add_argument(
        "--vt-model-type",
        choices=("viton_hd", "dress_code"),
        default="viton_hd",
        help="Leffa virtual try-on checkpoint family",
    )
    parser.add_argument(
        "--garment-type",
        choices=("upper_body", "lower_body", "dresses"),
        default="upper_body",
        help="Garment region passed to Leffa mask generation",
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
        help="Leffa guidance scale",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--ref-acceleration",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable Leffa reference UNet acceleration",
    )
    parser.add_argument(
        "--repaint",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable Leffa repaint mode",
    )
    parser.add_argument(
        "--preprocess-garment",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use Leffa garment preprocessing. Leffa upstream expects PNG inputs.",
    )
    parser.add_argument(
        "--allow-tf32",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow TF32 on compatible NVIDIA GPUs",
    )
    parser.add_argument(
        "--check-imports-only",
        action="store_true",
        help="Clone/use Leffa and validate imports, then exit before loading models",
    )
    parser.add_argument(
        "--download-checkpoints-only",
        action="store_true",
        help=(
            "Clone/use Leffa, download and validate checkpoints, then exit "
            "before loading models or reading input images"
        ),
    )
    args = parser.parse_args(argv)

    if args.report is None and args.output is None:
        parser.error("--output is required unless --report is provided")

    if not args.check_imports_only and not args.download_checkpoints_only:
        missing_options = []
        if args.person_image is None:
            missing_options.append("--person-image")
        if args.garment_image is None:
            missing_options.append("--garment-image")
        if args.output is None:
            missing_options.append("--output")
        if missing_options:
            parser.error(
                "the following arguments are required for generation: "
                + ", ".join(missing_options)
            )

    return args


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
            "Fix the RunPod image or PyTorch CUDA wheel before running Leffa."
        )

    try:
        device_name = torch.cuda.get_device_name(0)
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "CUDA was requested but the CUDA runtime could not initialize. "
            f"Original CUDA error: {exc!r}"
        ) from exc

    progress(f"cuda runtime ready: {device_name}")


def ensure_leffa_repo(*, leffa_root: Path, repo_url: str, no_clone: bool) -> None:
    if (leffa_root / "leffa" / "model.py").exists():
        progress(f"using Leffa repo at {leffa_root}")
        return

    if no_clone:
        raise FileNotFoundError(
            f"Leffa repo not found at {leffa_root}. "
            "Remove --no-clone or clone the repo manually."
        )

    leffa_root.parent.mkdir(parents=True, exist_ok=True)
    progress(f"cloning Leffa from {repo_url} to {leffa_root}")
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(leffa_root)],
        check=True,
    )


def load_leffa_modules(leffa_root: Path) -> dict[str, Any]:
    root = str(leffa_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from huggingface_hub import snapshot_download
        from leffa.inference import LeffaInference
        from leffa.model import LeffaModel
        from leffa.transform import LeffaTransform
        from leffa_utils.densepose_predictor import DensePosePredictor
        from leffa_utils.utils import get_agnostic_mask_dc
        from leffa_utils.utils import get_agnostic_mask_hd
        from leffa_utils.utils import preprocess_garment_image
        from leffa_utils.utils import resize_and_center
        from preprocess.humanparsing.run_parsing import Parsing
        from preprocess.openpose.run_openpose import OpenPose
    except ImportError as exc:
        raise RuntimeError(
            "Leffa dependencies are missing or incompatible. Run "
            "`make runpod-install-leffa-deps`, then retry the smoke. "
            f"Original import error: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "DensePosePredictor": DensePosePredictor,
        "LeffaInference": LeffaInference,
        "LeffaModel": LeffaModel,
        "LeffaTransform": LeffaTransform,
        "OpenPose": OpenPose,
        "Parsing": Parsing,
        "get_agnostic_mask_dc": get_agnostic_mask_dc,
        "get_agnostic_mask_hd": get_agnostic_mask_hd,
        "preprocess_garment_image": preprocess_garment_image,
        "resize_and_center": resize_and_center,
        "snapshot_download": snapshot_download,
    }


def download_leffa_checkpoints(
    *,
    modules: dict[str, Any],
    model_repo_id: str,
    ckpt_dir: Path,
) -> None:
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    progress(f"downloading/loading Leffa checkpoints from {model_repo_id}")
    modules["snapshot_download"](
        repo_id=model_repo_id,
        local_dir=str(ckpt_dir),
    )


def validate_leffa_checkpoint_assets(
    *,
    ckpt_dir: Path,
    vt_model_type: str,
) -> dict[str, str]:
    base_model_path = ckpt_dir / DEFAULT_BASE_MODEL_PATH
    pretrained_model = _virtual_tryon_checkpoint_path(ckpt_dir, vt_model_type)
    assets = {
        "base_model_path": base_model_path,
        "virtual_tryon_checkpoint": pretrained_model,
        "densepose_config": ckpt_dir / "densepose" / "densepose_rcnn_R_50_FPN_s1x.yaml",
        "densepose_weights": ckpt_dir / "densepose" / "model_final_162be9.pkl",
        "humanparsing_atr": ckpt_dir / "humanparsing" / "parsing_atr.onnx",
        "humanparsing_lip": ckpt_dir / "humanparsing" / "parsing_lip.onnx",
        "openpose_body_model": ckpt_dir / "openpose" / "body_pose_model.pth",
    }
    for label, path in assets.items():
        _ensure_checkpoint_exists(path, label.replace("_", " "))
    return {label: str(path) for label, path in assets.items()}


def _virtual_tryon_checkpoint_path(ckpt_dir: Path, vt_model_type: str) -> Path:
    return (
        ckpt_dir / DEFAULT_VIRTUAL_TRYON_MODEL
        if vt_model_type == "viton_hd"
        else ckpt_dir / DEFAULT_VIRTUAL_TRYON_DC_MODEL
    )


def generate_smoke(
    *,
    person_image: Path | None,
    garment_image: Path | None,
    output: Path | None,
    report: Path,
    leffa_root: Path,
    repo_url: str,
    no_clone: bool,
    model_repo_id: str,
    checkpoint_dir: Path | None,
    size: str,
    device: str,
    dtype: str,
    vt_model_type: str,
    garment_type: str,
    steps: int,
    guidance_scale: float,
    seed: int,
    ref_acceleration: bool,
    repaint: bool,
    preprocess_garment: bool,
    allow_tf32: bool,
    check_imports_only: bool = False,
    download_checkpoints_only: bool = False,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    started_monotonic = time.perf_counter()
    width, height = parse_size(size)
    if (width, height) != (768, 1024):
        raise ValueError(
            "Leffa upstream inference expects 768x1024. "
            f"Got {size}; use RUNPOD_LEFFA_SIZE=768x1024 for smoke."
        )

    resolved_device = device
    if not download_checkpoints_only:
        resolved_device = resolve_device(device)
        validate_device_runtime(resolved_device)
    ensure_leffa_repo(leffa_root=leffa_root, repo_url=repo_url, no_clone=no_clone)
    modules = load_leffa_modules(leffa_root)

    if check_imports_only:
        progress("Leffa imports passed")
        report_payload: dict[str, Any] = {
            "success": True,
            "finished_at": datetime.now(UTC).isoformat(),
            "model": "Leffa",
            "repo_url": repo_url,
            "leffa_root": str(leffa_root),
            "check_imports_only": True,
            "error": None,
        }
        _write_report(report, report_payload)
        return report_payload

    ckpt_dir = checkpoint_dir or leffa_root / "ckpts"
    download_leffa_checkpoints(
        modules=modules,
        model_repo_id=model_repo_id,
        ckpt_dir=ckpt_dir,
    )
    checkpoint_assets = validate_leffa_checkpoint_assets(
        ckpt_dir=ckpt_dir,
        vt_model_type=vt_model_type,
    )
    base_model_path = Path(checkpoint_assets["base_model_path"])
    pretrained_model = Path(checkpoint_assets["virtual_tryon_checkpoint"])

    if download_checkpoints_only:
        finished_at = datetime.now(UTC)
        report_payload = {
            "success": True,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "preload_time_seconds": time.perf_counter() - started_monotonic,
            "model": "Leffa",
            "repo_url": repo_url,
            "model_repo_id": model_repo_id,
            "leffa_root": str(leffa_root),
            "checkpoint_dir": str(ckpt_dir),
            "base_model_path": str(base_model_path),
            "pretrained_model": str(pretrained_model),
            "checkpoint_assets": checkpoint_assets,
            "size": size,
            "width": width,
            "height": height,
            "vt_model_type": vt_model_type,
            "download_checkpoints_only": True,
            "check_imports_only": False,
            "report": str(report),
            "error": None,
        }
        _write_report(report, report_payload)
        return report_payload

    if person_image is None:
        raise ValueError("person_image is required for Leffa generation")
    if garment_image is None:
        raise ValueError("garment_image is required for Leffa generation")
    if output is None:
        raise ValueError("output is required for Leffa generation")

    ensure_input_exists(person_image, "person image")
    ensure_input_exists(garment_image, "garment image")

    import torch

    if allow_tf32 and resolved_device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    progress("loading Leffa preprocessing modules")
    densepose_predictor = modules["DensePosePredictor"](
        config_path=str(ckpt_dir / "densepose" / "densepose_rcnn_R_50_FPN_s1x.yaml"),
        weights_path=str(ckpt_dir / "densepose" / "model_final_162be9.pkl"),
    )
    parsing = modules["Parsing"](
        atr_path=str(ckpt_dir / "humanparsing" / "parsing_atr.onnx"),
        lip_path=str(ckpt_dir / "humanparsing" / "parsing_lip.onnx"),
    )
    openpose = modules["OpenPose"](
        body_model_path=str(ckpt_dir / "openpose" / "body_pose_model.pth"),
    )

    progress(
        "loading Leffa model "
        f"(base={base_model_path}, checkpoint={pretrained_model}, dtype={dtype})"
    )
    model = modules["LeffaModel"](
        pretrained_model_name_or_path=str(base_model_path),
        pretrained_model=str(pretrained_model),
        dtype=dtype,
    )
    inference = modules["LeffaInference"](model=model)
    transform = modules["LeffaTransform"]()

    progress("preprocessing person and garment images")
    src_image = _load_rgb_image(person_image)
    src_image = modules["resize_and_center"](src_image, width, height)
    if preprocess_garment:
        if garment_image.suffix.lower() != ".png":
            raise ValueError(
                "Leffa preprocess_garment mode expects a PNG garment image. "
                "Disable --preprocess-garment for WEBP/JPEG smoke fixtures."
            )
        ref_image = modules["preprocess_garment_image"](str(garment_image))
    else:
        ref_image = _load_rgb_image(garment_image)
    ref_image = modules["resize_and_center"](ref_image, width, height)

    src_image_array = np.array(src_image)
    src_image = src_image.convert("RGB")
    model_parse, _ = parsing(src_image.resize((384, 512)))
    keypoints = openpose(src_image.resize((384, 512)))
    if vt_model_type == "viton_hd":
        mask = modules["get_agnostic_mask_hd"](model_parse, keypoints, garment_type)
        src_image_seg_array = densepose_predictor.predict_seg(src_image_array)[
            :, :, ::-1
        ]
        densepose = Image.fromarray(src_image_seg_array)
    else:
        mask = modules["get_agnostic_mask_dc"](model_parse, keypoints, garment_type)
        src_image_iuv_array = densepose_predictor.predict_iuv(src_image_array)
        src_image_seg_array = src_image_iuv_array[:, :, 0:1]
        src_image_seg_array = np.concatenate([src_image_seg_array] * 3, axis=-1)
        densepose = Image.fromarray(src_image_seg_array)
    mask = mask.resize((width, height))

    data = {
        "src_image": [src_image],
        "ref_image": [ref_image],
        "mask": [mask],
        "densepose": [densepose],
    }
    data = transform(data)

    if resolved_device == "cuda":
        try:
            torch.cuda.reset_peak_memory_stats()
        except Exception as exc:  # pragma: no cover - environment-specific
            progress(f"skipping cuda peak memory reset: {exc!r}")

    progress("generating image")
    with torch.inference_mode():
        inference_output = inference(
            data,
            ref_acceleration=ref_acceleration,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            seed=seed,
            repaint=repaint,
        )
    generated_image = inference_output["generated_image"][0]

    output.parent.mkdir(parents=True, exist_ok=True)
    generated_image.save(output)
    progress(f"saved {output}")

    mask_output = output.with_name(f"{output.stem}-mask.png")
    densepose_output = output.with_name(f"{output.stem}-densepose.png")
    mask.save(mask_output)
    densepose.save(densepose_output)

    finished_at = datetime.now(UTC)
    report_payload: dict[str, Any] = {
        "success": True,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "generation_time_seconds": time.perf_counter() - started_monotonic,
        "model": "Leffa",
        "repo_url": repo_url,
        "model_repo_id": model_repo_id,
        "leffa_root": str(leffa_root),
        "checkpoint_dir": str(ckpt_dir),
        "base_model_path": str(base_model_path),
        "pretrained_model": str(pretrained_model),
        "device": resolved_device,
        "dtype": dtype,
        "size": size,
        "width": width,
        "height": height,
        "vt_model_type": vt_model_type,
        "garment_type": garment_type,
        "steps": steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
        "ref_acceleration": ref_acceleration,
        "repaint": repaint,
        "preprocess_garment": preprocess_garment,
        "allow_tf32": allow_tf32,
        "person_image": str(person_image),
        "garment_image": str(garment_image),
        "output": str(output),
        "mask_output": str(mask_output),
        "densepose_output": str(densepose_output),
        "report": str(report),
        "runtime": collect_runtime_metrics(resolved_device),
        "manual_quality_scores": {
            "garment_fidelity": None,
            "web_garment_robustness": None,
            "human_preservation": None,
            "arm_sleeve_quality": None,
            "weighted_score": None,
            "verdict": "pending_manual_review",
        },
        "error": None,
    }
    _write_report(report, report_payload)
    return report_payload


def ensure_input_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def _ensure_checkpoint_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def _load_rgb_image(path: Path) -> Image.Image:
    ensure_input_exists(path, "input image")
    with Image.open(path) as image:
        return image.convert("RGB")


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    progress(f"wrote report {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report_path = args.report
    if report_path is None:
        if args.output is None:
            raise ValueError("--output is required unless --report is provided")
        report_path = args.output.with_suffix(f"{args.output.suffix}.json")
    checkpoint_dir = args.checkpoint_dir
    try:
        generate_smoke(
            person_image=args.person_image,
            garment_image=args.garment_image,
            output=args.output,
            report=report_path,
            leffa_root=args.leffa_root,
            repo_url=args.repo_url,
            no_clone=args.no_clone,
            model_repo_id=args.model_repo_id,
            checkpoint_dir=checkpoint_dir,
            size=args.size,
            device=args.device,
            dtype=args.dtype,
            vt_model_type=args.vt_model_type,
            garment_type=args.garment_type,
            steps=args.steps,
            guidance_scale=args.guidance_scale,
            seed=args.seed,
            ref_acceleration=args.ref_acceleration,
            repaint=args.repaint,
            preprocess_garment=args.preprocess_garment,
            allow_tf32=args.allow_tf32,
            check_imports_only=args.check_imports_only,
            download_checkpoints_only=args.download_checkpoints_only,
        )
        return 0
    except Exception as exc:
        failed_payload = {
            "success": False,
            "finished_at": datetime.now(UTC).isoformat(),
            "model": "Leffa",
            "repo_url": args.repo_url,
            "model_repo_id": args.model_repo_id,
            "leffa_root": str(args.leffa_root),
            "checkpoint_dir": str(checkpoint_dir) if checkpoint_dir else None,
            "device": args.device,
            "dtype": args.dtype,
            "size": args.size,
            "vt_model_type": args.vt_model_type,
            "garment_type": args.garment_type,
            "steps": args.steps,
            "guidance_scale": args.guidance_scale,
            "seed": args.seed,
            "ref_acceleration": args.ref_acceleration,
            "repaint": args.repaint,
            "preprocess_garment": args.preprocess_garment,
            "allow_tf32": args.allow_tf32,
            "check_imports_only": args.check_imports_only,
            "download_checkpoints_only": args.download_checkpoints_only,
            "person_image": str(args.person_image) if args.person_image else None,
            "garment_image": str(args.garment_image) if args.garment_image else None,
            "output": str(args.output) if args.output else None,
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
