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
    assert "RUNPOD_INSTALL_SYSTEM_DEPS=\"${RUNPOD_INSTALL_SYSTEM_DEPS:-1}\"" in script
    assert "install_nodejs" in script
    assert "https://deb.nodesource.com/node_20.x" in script
    assert "apt-get install -y nodejs" in script
    assert "make runpod-bootstrap" in script
    assert "npm ci" in script
    assert "npm run build" in script
    assert "API_PROFILE=\"${API_PROFILE:-kiosk}\"" in script
    assert "KIOSK_UI_ENABLED=\"${KIOSK_UI_ENABLED:-true}\"" in script
    assert "python -m scripts.run_kiosk_all" in script


def test_runpod_workflow_run_mode_bootstraps_before_building_ui():
    script = Path("scripts/workflow-runpod.sh").read_text("utf-8")

    run_block_start = script.index("  run)")
    run_block_end = script.index("  run-with-ollama)")
    run_block = script[run_block_start:run_block_end]

    assert run_block.index("switch_branch") < run_block.index("install_system_dependencies")
    assert run_block.index("install_system_dependencies") < run_block.index("bootstrap_runtime")
    assert run_block.index("bootstrap_runtime") < run_block.index("build_ui")
    assert run_block.index("build_ui") < run_block.index("run_api")


def test_runpod_workflow_run_mode_imports_default_size_charts_before_building_ui():
    script = Path("scripts/workflow-runpod.sh").read_text("utf-8")

    assert "import_default_size_charts" in script
    assert "make runpod-import-default-size-charts" in script

    run_block_start = script.index("  run)")
    run_block_end = script.index("  run-with-ollama)")
    run_block = script[run_block_start:run_block_end]

    assert run_block.index("bootstrap_runtime") < run_block.index(
        "import_default_size_charts"
    )
    assert run_block.index("import_default_size_charts") < run_block.index("build_ui")


def test_runpod_workflow_run_mode_imports_default_garments_after_size_charts():
    script = Path("scripts/workflow-runpod.sh").read_text("utf-8")

    assert "import_default_garments" in script
    assert "make runpod-import-default-garments" in script

    run_block_start = script.index("  run)")
    run_block_end = script.index("  run-with-ollama)")
    run_block = script[run_block_start:run_block_end]

    assert run_block.index("import_default_size_charts") < run_block.index(
        "import_default_garments"
    )
    assert run_block.index("import_default_garments") < run_block.index("build_ui")


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


def test_runpod_import_default_size_charts_target_uses_runpod_data_dir():
    result = subprocess.run(
        ["make", "-n", "runpod-import-default-size-charts"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "python -m scripts.seed_size_charts" in result.stdout
    assert "--db-path /workspace/tryon-data/size_charts/size_charts.sqlite3" in result.stdout


def test_runpod_import_default_garments_target_uses_runpod_data_dir():
    result = subprocess.run(
        ["make", "-n", "runpod-import-default-garments"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "python -m scripts.seed_garment_catalog" in result.stdout
    assert "--source-dir data/garment_catalog" in result.stdout
    assert "--storage-dir /workspace/tryon-data/garments" in result.stdout
    assert "--size-chart-db-path /workspace/tryon-data/size_charts/size_charts.sqlite3" in result.stdout
