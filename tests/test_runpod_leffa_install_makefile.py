import os
from pathlib import Path
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


def test_runpod_workflow_script_switches_gpu_flow_branch_and_builds_ui():
    script = Path("scripts/workflow-runpod.sh").read_text("utf-8")

    assert "RUNPOD_BRANCH=\"${RUNPOD_BRANCH:-feature/kiosk-gpu-flow}\"" in script
    assert 'git switch "$RUNPOD_BRANCH"' in script
    assert "npm ci" in script
    assert "npm run build" in script
    assert "API_PROFILE=\"${API_PROFILE:-kiosk}\"" in script
    assert "KIOSK_UI_ENABLED=\"${KIOSK_UI_ENABLED:-true}\"" in script
    assert "python -m scripts.run_kiosk_all" in script


def test_runpod_workflow_make_targets_call_script():
    result = subprocess.run(
        ["make", "-n", "runpod-workflow"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "bash scripts/workflow-runpod.sh run" in result.stdout

    build_result = subprocess.run(
        ["make", "-n", "runpod-build"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "bash scripts/workflow-runpod.sh build" in build_result.stdout
