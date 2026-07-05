import os
import subprocess


def test_leffa_torch_install_does_not_force_reinstall_by_default():
    result = subprocess.run(
        ["make", "-n", "runpod-install-leffa-torch-cu124"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--force-reinstall" not in result.stdout


def test_leffa_torch_install_force_reinstall_is_explicit():
    env = os.environ.copy()
    env["RUNPOD_LEFFA_FORCE_REINSTALL"] = "1"

    result = subprocess.run(
        ["make", "-n", "runpod-install-leffa-torch-cu124"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "--force-reinstall" in result.stdout


def test_leffa_preload_downloads_checkpoints_without_smoke_generation():
    result = subprocess.run(
        ["make", "-n", "runpod-leffa-preload"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "$(RUNPOD_LEFFA_PYTHON)" not in result.stdout
    assert "/workspace/tryon-models/venvs/leffa/bin/python" in result.stdout
    assert "--download-checkpoints-only" in result.stdout
    assert "--check-imports-only" not in result.stdout
    assert "--checkpoint-dir" in result.stdout
    assert "/workspace/tryon-models/external/Leffa/ckpts" in result.stdout


def test_runpod_start_command_can_enable_local_visual_engine_service():
    result = subprocess.run(
        ["make", "-n", "runpod-start"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "scripts.run_kiosk_all" in result.stdout
    assert "LOCAL_VISUAL_ENGINE_START_SERVICE" not in result.stdout
