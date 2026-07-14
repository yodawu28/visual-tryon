from pathlib import Path


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


def test_leffa_install_uses_isolated_runtime_check_and_constraints() -> None:
    makefile = Path("Makefile").read_text("utf-8")
    leffa_install = _target_block("runpod-install-leffa-deps", makefile)

    assert "RUNPOD_LEFFA_CONSTRAINTS ?= constraints-leffa-runpod.txt" in makefile
    assert '"$(RUNPOD_LEFFA_PYTHON)" -m scripts.check_leffa_runtime' in leffa_install
    assert "$(RUNPOD_PIP_INSTALL_FLAGS)" in leffa_install
    assert '-c "$(RUNPOD_LEFFA_CONSTRAINTS)"' in leffa_install
    assert '-r "$(RUNPOD_LEFFA_REQUIREMENTS)"' in leffa_install


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
