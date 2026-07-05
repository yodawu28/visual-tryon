import os
import subprocess
import sys
from pathlib import Path

import pytest

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
