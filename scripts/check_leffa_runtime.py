"""Check whether the isolated Leffa runtime is already usable.

This script is intentionally lightweight: it verifies package presence and the
expected torch wheel versions without loading Leffa model weights.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata as metadata
import importlib.util
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeRequirement:
    dist_name: str
    import_name: str
    version_prefix: str | None = None
    must_import: bool = False


TORCH_REQUIREMENTS = (
    RuntimeRequirement("torch", "torch", "2.6.0", must_import=True),
    RuntimeRequirement("torchvision", "torchvision", "0.21.0", must_import=True),
    RuntimeRequirement("torchaudio", "torchaudio", "2.6.0", must_import=True),
)

LEFFA_REQUIREMENTS = (
    RuntimeRequirement("accelerate", "accelerate"),
    RuntimeRequirement("av", "av"),
    RuntimeRequirement("cloudpickle", "cloudpickle"),
    RuntimeRequirement("diffusers", "diffusers"),
    RuntimeRequirement("einops", "einops"),
    RuntimeRequirement("fvcore", "fvcore"),
    RuntimeRequirement("huggingface_hub", "huggingface_hub"),
    RuntimeRequirement("imageio", "imageio"),
    RuntimeRequirement("iopath", "iopath"),
    RuntimeRequirement("matplotlib", "matplotlib"),
    RuntimeRequirement("numpy", "numpy", "1.26.4"),
    RuntimeRequirement("omegaconf", "omegaconf"),
    RuntimeRequirement("onnxruntime", "onnxruntime"),
    RuntimeRequirement("opencv-python-headless", "cv2", "4.10.0.84"),
    RuntimeRequirement("packaging", "packaging"),
    RuntimeRequirement("pandas", "pandas"),
    RuntimeRequirement("peft", "peft"),
    RuntimeRequirement("pillow", "PIL"),
    RuntimeRequirement("psutil", "psutil"),
    RuntimeRequirement("pycocotools", "pycocotools"),
    RuntimeRequirement("PyYAML", "yaml"),
    RuntimeRequirement("regex", "regex", "2024.5.15"),
    RuntimeRequirement("safetensors", "safetensors"),
    RuntimeRequirement("scikit-image", "skimage"),
    RuntimeRequirement("scipy", "scipy"),
    RuntimeRequirement("tabulate", "tabulate"),
    RuntimeRequirement("termcolor", "termcolor"),
    RuntimeRequirement("timm", "timm"),
    RuntimeRequirement("tokenizers", "tokenizers"),
    RuntimeRequirement("torchmetrics", "torchmetrics"),
    RuntimeRequirement("tqdm", "tqdm"),
    RuntimeRequirement("transformers", "transformers"),
    RuntimeRequirement("yacs", "yacs"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--torch-only",
        action="store_true",
        help="Check only the Leffa torch stack.",
    )
    parser.add_argument(
        "--require-cuda",
        action="store_true",
        help="Fail when torch imports but CUDA is not available.",
    )
    args = parser.parse_args()

    requirements = list(TORCH_REQUIREMENTS)
    if not args.torch_only:
        requirements.extend(LEFFA_REQUIREMENTS)

    issues = _collect_issues(requirements)
    if args.require_cuda and not issues:
        issues.extend(_cuda_issues())

    if issues:
        print("[leffa-runtime] not ready")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    scope = "torch stack" if args.torch_only else "runtime"
    print(f"[leffa-runtime] {scope} ready")
    return 0


def _collect_issues(requirements: list[RuntimeRequirement]) -> list[str]:
    issues: list[str] = []
    for requirement in requirements:
        try:
            version = metadata.version(requirement.dist_name)
        except metadata.PackageNotFoundError:
            issues.append(f"missing package: {requirement.dist_name}")
            continue

        if requirement.version_prefix and not version.startswith(
            requirement.version_prefix
        ):
            issues.append(
                "version mismatch: "
                f"{requirement.dist_name} expected {requirement.version_prefix}*, "
                f"got {version}"
            )

        if requirement.must_import:
            try:
                importlib.import_module(requirement.import_name)
            except Exception as exc:  # pragma: no cover - depends on runtime wheels
                issues.append(
                    f"import failed: {requirement.import_name}: "
                    f"{type(exc).__name__}: {exc}"
                )
        elif importlib.util.find_spec(requirement.import_name) is None:
            issues.append(f"missing import module: {requirement.import_name}")

    return issues


def _cuda_issues() -> list[str]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - depends on runtime wheels
        return [f"torch import failed during CUDA check: {type(exc).__name__}: {exc}"]

    try:
        cuda_available = torch.cuda.is_available()
    except Exception as exc:  # pragma: no cover - depends on runtime wheels
        return [f"torch CUDA check failed: {type(exc).__name__}: {exc}"]

    if cuda_available:
        return []

    cuda_build = getattr(torch.version, "cuda", None)
    return [f"CUDA unavailable for torch build {cuda_build or 'unknown'}"]


if __name__ == "__main__":
    raise SystemExit(main())
