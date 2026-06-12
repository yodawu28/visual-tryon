"""
Smoke/preflight OmniVTON local inference on a GPU machine.

OmniVTON is not a simple person+garment VTON CLI. The official VTON stage
requires masks, CLIP-interrogator prompt JSON files, TAPPS parsing maps, and
OpenPose keypoint JSON files. This harness makes that contract explicit and
fails before model loading when the required condition assets are missing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from scripts.local_qwen_edit_smoke import collect_runtime_metrics
from scripts.local_qwen_edit_smoke import parse_size


DEFAULT_REPO_URL = "https://github.com/Jerome-Young/OmniVTON.git"


def progress(message: str) -> None:
    print(f"[local-omnivton] {message}", flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one local OmniVTON smoke")
    parser.add_argument("--person-image", required=True, type=Path)
    parser.add_argument("--garment-image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--omnivton-root", required=True, type=Path)
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--no-clone", action="store_true")
    parser.add_argument(
        "--stage",
        choices=("preflight", "outpainting", "vton"),
        default="preflight",
        help=(
            "preflight validates repo/dependency/condition contracts only; "
            "outpainting runs OmniVTON stage 1; vton runs final VTON stage and "
            "requires full TAPPS/OpenPose condition assets."
        ),
    )
    parser.add_argument(
        "--model-id", choices=("sd2_inp", "sd15_inp"), default="sd2_inp"
    )
    parser.add_argument("--size", default="384x512", help="WIDTHxHEIGHT")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--steps", type=_positive_int, default=30)
    parser.add_argument("--guidance-scale", type=float, default=7.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--condition-dir",
        type=Path,
        help="Existing OmniVTON condition directory. Defaults to <work-dir>/condition.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Work directory for converted JPG inputs and generated rough masks.",
    )
    parser.add_argument("--in-mask-image", type=Path)
    parser.add_argument("--out-mask-image", type=Path)
    parser.add_argument(
        "--auto-rough-masks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create rough upper-body masks for stage contract/runtime checks.",
    )
    parser.add_argument(
        "--auto-prompt-json",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create minimal CLIP-interrogator JSON files for runtime smoke.",
    )
    parser.add_argument(
        "--check-imports-only",
        action="store_true",
        help="Clone/use OmniVTON and validate imports, then exit before model loading.",
    )
    return parser.parse_args(argv)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def resolve_device(requested_device: str) -> str:
    if requested_device != "auto":
        return requested_device
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def validate_device_runtime(device: str) -> None:
    if device != "cuda":
        return
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA was requested but torch.cuda.is_available() is false. "
            "Fix the RunPod image or PyTorch CUDA wheel before running OmniVTON."
        )
    progress(f"cuda runtime ready: {torch.cuda.get_device_name(0)}")


def ensure_omnivton_repo(*, omnivton_root: Path, repo_url: str, no_clone: bool) -> None:
    if (omnivton_root / "inference.py").exists() and (omnivton_root / "src").exists():
        progress(f"using OmniVTON repo at {omnivton_root}")
        return
    if no_clone:
        raise FileNotFoundError(
            f"OmniVTON repo not found at {omnivton_root}. "
            "Remove --no-clone or clone it manually."
        )
    omnivton_root.parent.mkdir(parents=True, exist_ok=True)
    progress(f"cloning OmniVTON from {repo_url} to {omnivton_root}")
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(omnivton_root)], check=True
    )


def validate_imports(omnivton_root: Path) -> None:
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(omnivton_root.resolve())!r}); "
        "import inference"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def ensure_input_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def prepare_work_inputs(
    *,
    person_image: Path,
    garment_image: Path,
    work_dir: Path,
    size: str,
    auto_rough_masks: bool,
    in_mask_image: Path | None,
    out_mask_image: Path | None,
    condition_dir: Path,
    auto_prompt_json: bool,
) -> dict[str, Path]:
    ensure_input_exists(person_image, "person image")
    ensure_input_exists(garment_image, "garment image")
    width, height = parse_size(size)
    work_dir.mkdir(parents=True, exist_ok=True)
    condition_dir.mkdir(parents=True, exist_ok=True)

    prepared_person = work_dir / "person.jpg"
    prepared_garment = work_dir / "cloth.jpg"
    _convert_rgb(person_image, prepared_person)
    _convert_rgb(garment_image, prepared_garment)

    in_mask = in_mask_image or work_dir / "person_mask.png"
    out_mask = out_mask_image or work_dir / "cloth_mask.png"
    if auto_rough_masks:
        if in_mask_image is None:
            _create_upper_body_mask(in_mask, (width, height))
        if out_mask_image is None:
            _create_upper_body_mask(out_mask, (width, height))
    ensure_input_exists(in_mask, "OmniVTON in/person mask")
    ensure_input_exists(out_mask, "OmniVTON out/cloth mask")

    if auto_prompt_json:
        _write_prompt_jsons(condition_dir)
    _validate_prompt_jsons(condition_dir)

    return {
        "person": prepared_person,
        "garment": prepared_garment,
        "in_mask": in_mask,
        "out_mask": out_mask,
        "condition_dir": condition_dir,
    }


def _convert_rgb(source: Path, target: Path) -> None:
    with Image.open(source) as image:
        target.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(target, quality=95)


def _create_upper_body_mask(path: Path, size: tuple[int, int]) -> None:
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (
            round(width * 0.13),
            round(height * 0.15),
            round(width * 0.87),
            round(height * 0.68),
        ),
        radius=max(4, width // 28),
        fill=255,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(path)


def _write_prompt_jsons(condition_dir: Path) -> None:
    image_dir = condition_dir / "image_clip_interrogate"
    cloth_dir = condition_dir / "cloth_clip_interrogate"
    image_dir.mkdir(parents=True, exist_ok=True)
    cloth_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / "person_ci.json").write_text(
        json.dumps(
            {"cloth_clip_interrogate": "a person wearing a simple upper-body garment"},
            indent=2,
        ),
        "utf-8",
    )
    (cloth_dir / "cloth_ci.json").write_text(
        json.dumps(
            {
                "cloth_clip_interrogate": (
                    "a short sleeve upper-body shirt with visible printed logo, "
                    "text, and fabric details"
                )
            },
            indent=2,
        ),
        "utf-8",
    )


def _validate_prompt_jsons(condition_dir: Path) -> None:
    required = [
        condition_dir / "image_clip_interrogate" / "person_ci.json",
        condition_dir / "cloth_clip_interrogate" / "cloth_ci.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing OmniVTON clip-interrogator prompt JSON files: "
            + ", ".join(missing)
        )


def validate_vton_condition_assets(condition_dir: Path) -> None:
    required = [
        condition_dir / "image_tapps_parse" / "person_pps.png",
        condition_dir / "cloth_tapps_parse" / "cloth_pps.png",
        condition_dir / "image_openpose_json" / "person_keypoints.json",
        condition_dir / "cloth_openpose_json" / "cloth_keypoints.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "OmniVTON full VTON stage requires TAPPS parsing maps and OpenPose "
            "keypoint JSON files. Missing: "
            + ", ".join(missing)
            + ". Run stage=outpainting only for runtime smoke, or add a condition "
            "asset generator before evaluating OmniVTON quality."
        )


def run_omnivton_inference(
    *,
    omnivton_root: Path,
    prepared: dict[str, Path],
    output: Path,
    stage: str,
    model_id: str,
    size: str,
    steps: int,
    guidance_scale: float,
    seed: int,
) -> Path:
    width, height = parse_size(size)
    inference_output_dir = output.parent / f"{output.stem}-omnivton-output"
    command = [
        sys.executable,
        "inference.py",
        "--model-id",
        model_id,
        "--image-path",
        str(prepared["person"]),
        "--cloth-path",
        str(prepared["garment"]),
        "--in-mask-path",
        str(prepared["in_mask"]),
        "--out-mask-path",
        str(prepared["out_mask"]),
        "--condition-path",
        str(prepared["condition_dir"]),
        "--stage",
        stage,
        "--H",
        str(height),
        "--W",
        str(width),
        "--output-path",
        str(inference_output_dir),
        "--num-steps",
        str(steps),
        "--guidance-scale",
        str(guidance_scale),
        "--seed",
        str(seed),
    ]
    progress("running OmniVTON " + stage)
    subprocess.run(command, cwd=str(omnivton_root), check=True)

    generated = (
        inference_output_dir / "vton" / "person.jpg"
        if stage == "vton"
        else inference_output_dir / "outpainting" / "cloth.jpg"
    )
    ensure_input_exists(generated, "OmniVTON generated output")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated, output)
    return generated


def generate_smoke(
    *,
    args: argparse.Namespace,
    report: Path,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    started_monotonic = time.perf_counter()
    resolved_device = resolve_device(args.device)
    if args.stage != "preflight":
        validate_device_runtime(resolved_device)

    ensure_omnivton_repo(
        omnivton_root=args.omnivton_root,
        repo_url=args.repo_url,
        no_clone=args.no_clone,
    )
    validate_imports(args.omnivton_root)

    if args.check_imports_only or args.stage == "preflight":
        payload = _base_report(args, report, started_at, resolved_device)
        payload.update(
            {
                "success": True,
                "finished_at": datetime.now(UTC).isoformat(),
                "generation_time_seconds": time.perf_counter() - started_monotonic,
                "check_imports_only": args.check_imports_only,
                "preflight_only": args.stage == "preflight",
                "error": None,
            }
        )
        _write_report(report, payload)
        return payload

    work_dir = args.work_dir or args.output.parent / f"{args.output.stem}-work"
    condition_dir = args.condition_dir or work_dir / "condition"
    prepared = prepare_work_inputs(
        person_image=args.person_image,
        garment_image=args.garment_image,
        work_dir=work_dir,
        size=args.size,
        auto_rough_masks=args.auto_rough_masks,
        in_mask_image=args.in_mask_image,
        out_mask_image=args.out_mask_image,
        condition_dir=condition_dir,
        auto_prompt_json=args.auto_prompt_json,
    )
    if args.stage == "vton":
        validate_vton_condition_assets(condition_dir)

    generated = run_omnivton_inference(
        omnivton_root=args.omnivton_root,
        prepared=prepared,
        output=args.output,
        stage=args.stage,
        model_id=args.model_id,
        size=args.size,
        steps=args.steps,
        guidance_scale=args.guidance_scale,
        seed=args.seed,
    )

    payload = _base_report(args, report, started_at, resolved_device)
    payload.update(
        {
            "success": True,
            "finished_at": datetime.now(UTC).isoformat(),
            "generation_time_seconds": time.perf_counter() - started_monotonic,
            "work_dir": str(work_dir),
            "condition_dir": str(condition_dir),
            "prepared_inputs": {key: str(value) for key, value in prepared.items()},
            "generated_intermediate": str(generated),
            "output": str(args.output),
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
    )
    _write_report(report, payload)
    return payload


def _base_report(
    args: argparse.Namespace,
    report: Path,
    started_at: datetime,
    resolved_device: str,
) -> dict[str, Any]:
    width, height = parse_size(args.size)
    return {
        "model": "OmniVTON",
        "repo_url": args.repo_url,
        "omnivton_root": str(args.omnivton_root),
        "stage": args.stage,
        "model_id": args.model_id,
        "device": resolved_device,
        "size": args.size,
        "width": width,
        "height": height,
        "steps": args.steps,
        "guidance_scale": args.guidance_scale,
        "seed": args.seed,
        "person_image": str(args.person_image),
        "garment_image": str(args.garment_image),
        "output": str(args.output),
        "report": str(report),
        "started_at": started_at.isoformat(),
        "condition_requirements": {
            "clip_interrogator_json": "required",
            "agnostic_person_mask": "required",
            "clothing_mask": "required",
            "tapps_parse_maps_for_vton_stage": "required",
            "openpose_keypoints_for_vton_stage": "required",
        },
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
    progress(f"wrote report {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = args.report or args.output.with_suffix(f"{args.output.suffix}.json")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    try:
        generate_smoke(args=args, report=report)
        return 0
    except Exception as exc:
        failed_payload = _base_report(
            args,
            report,
            datetime.now(UTC),
            args.device,
        )
        failed_payload.update(
            {
                "success": False,
                "finished_at": datetime.now(UTC).isoformat(),
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            }
        )
        _write_report(report, failed_payload)
        progress(f"failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
