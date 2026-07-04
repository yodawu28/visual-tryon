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
