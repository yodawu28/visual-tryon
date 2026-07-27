from pathlib import Path
import subprocess
import sys


def test_runpod_bootstrap_installs_app_and_leffa_runtime() -> None:
    makefile = Path("Makefile").read_text("utf-8")

    assert "runpod-bootstrap" in _phony_targets(makefile)
    assert "runpod-bootstrap: runpod-install runpod-install-leffa-deps" in makefile
    assert "make runpod-bootstrap" in makefile


def test_kiosk_install_uses_cached_binary_constrained_resolution() -> None:
    install_kiosk = _target_block("install-kiosk", Path("Makefile").read_text("utf-8"))

    assert 'PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)"' in install_kiosk
    assert "$(RUNPOD_PIP_INSTALL_FLAGS)" in install_kiosk
    assert "-c $(RUNPOD_KIOSK_CONSTRAINTS)" in install_kiosk
    assert "-r $(RUNPOD_REQUIREMENTS)" in install_kiosk
    assert "scripts.install_state" in install_kiosk
    assert "check; then" in install_kiosk
    assert "write; \\" in install_kiosk
    assert "RUNPOD_FORCE_INSTALL" in install_kiosk


def test_leffa_install_uses_isolated_runtime_check_and_constraints() -> None:
    makefile = Path("Makefile").read_text("utf-8")
    leffa_install = _target_block("runpod-install-leffa-deps", makefile)
    leffa_torch_install = _target_block("runpod-install-leffa-torch-cu124", makefile)

    assert "RUNPOD_LEFFA_CONSTRAINTS ?= constraints-leffa-runpod.txt" in makefile
    assert '"$(RUNPOD_LEFFA_PYTHON)" -m scripts.check_leffa_runtime' in leffa_install
    assert "$(RUNPOD_PIP_INSTALL_FLAGS)" in leffa_install
    assert '-c "$(RUNPOD_LEFFA_CONSTRAINTS)"' in leffa_install
    assert '-r "$(RUNPOD_LEFFA_REQUIREMENTS)"' in leffa_install
    assert "scripts.install_state" in leffa_install
    assert "check; then" in leffa_install
    assert "write; \\" in leffa_install
    assert "scripts.install_state" in leffa_torch_install
    assert "check; then" in leffa_torch_install
    assert "write; \\" in leffa_torch_install
    assert "RUNPOD_FORCE_INSTALL" in leffa_install


def test_dependency_constraints_pin_runtime_profiles_without_cross_installing_torch() -> None:
    kiosk_constraints = Path("constraints-kiosk.txt").read_text("utf-8")
    leffa_constraints = Path("constraints-leffa-runpod.txt").read_text("utf-8")
    leffa_requirements = Path("requirements-leffa-runpod.txt").read_text("utf-8")
    leffa_checker = Path("scripts/check_leffa_runtime.py").read_text("utf-8")

    assert "fastapi==0.115.5" in kiosk_constraints
    assert "mediapipe==0.10.21" in kiosk_constraints
    assert "torch==" not in kiosk_constraints

    assert "diffusers==0.32.2" in leffa_constraints
    assert "hf_transfer==" in leffa_constraints
    assert "hf_transfer>=" in leffa_requirements
    assert 'RuntimeRequirement("hf_transfer", "hf_transfer")' in leffa_checker
    assert "transformers==4.46.3" in leffa_constraints
    assert "torch==" not in leffa_constraints
    assert "torchvision==" not in leffa_constraints


def test_install_state_detects_unchanged_and_changed_dependency_inputs(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "install-state"
    requirements = tmp_path / "requirements.txt"
    constraints = tmp_path / "constraints.txt"
    requirements.write_text("fastapi==0.115.5\n", encoding="utf-8")
    constraints.write_text("pydantic==2.10.6\n", encoding="utf-8")

    base_command = [
        sys.executable,
        "-m",
        "scripts.install_state",
        "--state-dir",
        str(state_dir),
        "--name",
        "kiosk-python",
        "--path",
        str(requirements),
        "--path",
        str(constraints),
        "--value",
        "pip-flags=--prefer-binary",
    ]

    missing_state = subprocess.run(
        [*base_command, "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing_state.returncode == 1

    subprocess.run([*base_command, "write"], check=True)
    unchanged_state = subprocess.run(
        [*base_command, "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert unchanged_state.returncode == 0

    requirements.write_text("fastapi==0.116.0\n", encoding="utf-8")
    changed_state = subprocess.run(
        [*base_command, "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert changed_state.returncode == 1


def _phony_targets(makefile: str) -> set[str]:
    phony_line = next(line for line in makefile.splitlines() if line.startswith(".PHONY:"))
    return set(phony_line.removeprefix(".PHONY:").split())


def _target_block(target: str, makefile: str) -> str:
    lines = makefile.splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.startswith(f"{target}:")
    )
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith(("\t", " ", "@")) and ":" in line:
            end = index
            break
    return "\n".join(lines[start:end])
