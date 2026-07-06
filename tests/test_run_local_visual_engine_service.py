import os
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.run_local_visual_engine_service as run_local_visual_engine_service
from scripts.run_local_visual_engine_service import build_engine_from_env
from src.modules.local_visual_engine.leffa_engine import LeffaVisualEngine


def test_build_engine_from_env_builds_leffa_engine(monkeypatch, tmp_path):
    leffa_root = tmp_path / "Leffa"
    checkpoint_dir = tmp_path / "ckpts"
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_ENGINE", "leffa")
    monkeypatch.setenv("LOCAL_LEFFA_ROOT", str(leffa_root))
    monkeypatch.setenv("LOCAL_LEFFA_REPO_URL", "https://example.test/leffa.git")
    monkeypatch.setenv("LOCAL_LEFFA_NO_CLONE", "false")
    monkeypatch.setenv("LOCAL_LEFFA_MODEL_REPO_ID", "example/leffa")
    monkeypatch.setenv("LOCAL_LEFFA_CHECKPOINT_DIR", str(checkpoint_dir))
    monkeypatch.setenv("LOCAL_LEFFA_SIZE", "512x768")
    monkeypatch.setenv("LOCAL_LEFFA_DEVICE", "cpu")
    monkeypatch.setenv("LOCAL_LEFFA_DTYPE", "float32")
    monkeypatch.setenv("LOCAL_LEFFA_VT_MODEL_TYPE", "dress")

    engine = build_engine_from_env()

    assert isinstance(engine, LeffaVisualEngine)
    assert engine.leffa_root == Path(leffa_root)
    assert engine.repo_url == "https://example.test/leffa.git"
    assert engine.no_clone is False
    assert engine.model_repo_id == "example/leffa"
    assert engine.checkpoint_dir == Path(checkpoint_dir)
    assert engine.size == "512x768"
    assert engine.device == "cpu"
    assert engine.dtype == "float32"
    assert engine.vt_model_type == "dress"
    assert engine.allow_tf32 is True


def test_build_engine_from_env_rejects_unknown_engine(monkeypatch):
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_ENGINE", "unknown")

    with pytest.raises(ValueError, match="supports only leffa"):
        build_engine_from_env()


def test_apply_leffa_cache_env_maps_persistent_cache_paths(monkeypatch):
    monkeypatch.setenv("LOCAL_LEFFA_HF_HOME", "/workspace/tryon-models/huggingface")
    monkeypatch.setenv("LOCAL_LEFFA_TORCH_HOME", "/workspace/tryon-models/torch")
    monkeypatch.setenv(
        "LOCAL_LEFFA_XDG_CACHE_HOME", "/workspace/tryon-models/xdg-cache"
    )
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.delenv("TORCH_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("PYTORCH_CUDA_ALLOC_CONF", raising=False)

    run_local_visual_engine_service.apply_leffa_runtime_env()

    assert os.environ["HF_HOME"] == "/workspace/tryon-models/huggingface"
    assert (
        os.environ["TRANSFORMERS_CACHE"]
        == "/workspace/tryon-models/huggingface/transformers"
    )
    assert (
        os.environ["HUGGINGFACE_HUB_CACHE"] == "/workspace/tryon-models/huggingface/hub"
    )
    assert os.environ["TORCH_HOME"] == "/workspace/tryon-models/torch"
    assert os.environ["XDG_CACHE_HOME"] == "/workspace/tryon-models/xdg-cache"
    assert os.environ["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"


def test_validate_bind_host_rejects_non_loopback_without_override(monkeypatch):
    monkeypatch.delenv("LOCAL_VISUAL_ENGINE_ALLOW_UNSAFE_BIND", raising=False)

    with pytest.raises(ValueError, match="loopback"):
        run_local_visual_engine_service.validate_bind_host("0.0.0.0")


def test_validate_bind_host_allows_non_loopback_with_explicit_override(monkeypatch):
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_ALLOW_UNSAFE_BIND", "true")

    run_local_visual_engine_service.validate_bind_host("0.0.0.0")


def test_direct_script_help_lists_cli_options():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_local_visual_engine_service.py",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--log-level" in result.stdout


def test_direct_script_help_tolerates_malformed_env_defaults():
    env = _malformed_cli_default_env()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_local_visual_engine_service.py",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--log-level" in result.stdout


def test_module_help_tolerates_malformed_env_defaults():
    env = _malformed_cli_default_env()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_local_visual_engine_service",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--log-level" in result.stdout


def test_main_defers_service_import_until_after_parse_args():
    source = Path("scripts/run_local_visual_engine_service.py").read_text("utf-8")
    main_index = source.index("def main()")
    parse_args_index = source.index("args = parse_args()", main_index)
    service_import_index = source.index(
        "from src.modules.local_visual_engine.service import "
        "LocalVisualEngineHTTPServer",
        main_index,
    )

    assert parse_args_index < service_import_index


def _malformed_cli_default_env() -> dict[str, str]:
    env = os.environ.copy()
    env["LOCAL_VISUAL_ENGINE_SERVICE_PORT"] = "abc"
    env["LOG_LEVEL"] = "TRACE"
    return env
