"""Print RunPod PyTorch/CUDA diagnostics for local model smoke tests."""

from __future__ import annotations

import importlib.metadata
import subprocess
from typing import Iterable


def _print_header(title: str) -> None:
    print(f"== {title} ==")


def _run_command(command: Iterable[str]) -> None:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        print(f"command not found: {exc.filename}")
        return

    output = completed.stdout.strip()
    if output:
        print(output)
    print(f"exit_code={completed.returncode}")


def _package_version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def print_torch_report() -> None:
    try:
        import torch
    except Exception as exc:
        print(f"torch import error: {exc!r}")
        return

    print(f"torch package: {_package_version('torch')}")
    print(f"torch __version__: {torch.__version__}")
    print(f"torch cuda build: {torch.version.cuda}")

    try:
        print(f"cuda available: {torch.cuda.is_available()}")
    except Exception as exc:
        print(f"cuda available error: {exc!r}")

    try:
        print(f"cuda device count: {torch.cuda.device_count()}")
    except Exception as exc:
        print(f"cuda device count error: {exc!r}")

    try:
        if torch.cuda.is_available():
            print(f"cuda device 0: {torch.cuda.get_device_name(0)}")
    except Exception as exc:
        print(f"cuda init error: {exc!r}")


def print_torchvision_report() -> None:
    print(f"torchvision package: {_package_version('torchvision')}")
    try:
        import torchvision
    except Exception as exc:
        print(f"torchvision import error: {exc!r}")
        return

    print(f"torchvision __version__: {torchvision.__version__}")


def main() -> int:
    _print_header("nvidia-smi")
    _run_command(["nvidia-smi"])
    print()

    _print_header("torch cuda probe")
    print_torch_report()
    print_torchvision_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
