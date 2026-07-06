from __future__ import annotations

import os
from pathlib import Path


def load_runtime_env(
    dotenv_path: Path | str = ".env",
    *,
    update_environ: bool = False,
) -> dict[str, str]:
    env = os.environ.copy()
    values = _read_dotenv(Path(dotenv_path))
    for key, value in values.items():
        env.setdefault(key, value)
        if update_environ:
            os.environ.setdefault(key, value)
    return env


def apply_leffa_runtime_env() -> None:
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    hf_home = os.environ.get("LOCAL_LEFFA_HF_HOME")
    if hf_home:
        hf_path = Path(hf_home)
        os.environ["HF_HOME"] = str(hf_path)
        os.environ["TRANSFORMERS_CACHE"] = str(hf_path / "transformers")
        os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_path / "hub")

    torch_home = os.environ.get("LOCAL_LEFFA_TORCH_HOME")
    if torch_home:
        os.environ["TORCH_HOME"] = torch_home

    xdg_cache_home = os.environ.get("LOCAL_LEFFA_XDG_CACHE_HOME")
    if xdg_cache_home:
        os.environ["XDG_CACHE_HOME"] = xdg_cache_home


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _normalize_dotenv_value(value.strip())
    return values


def _normalize_dotenv_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
