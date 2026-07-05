import sys

from scripts.run_kiosk_all import (
    build_api_command,
    build_local_visual_engine_service_command,
    build_ollama_command,
    build_worker_command,
)


def test_build_api_command_uses_kiosk_host_and_port() -> None:
    command = build_api_command(host="0.0.0.0", port=8080)

    assert command == [
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ]


def test_build_worker_command_uses_expected_module_and_options() -> None:
    command = build_worker_command(
        poll_interval_seconds=1.5,
        stale_running_seconds=600,
        log_level="DEBUG",
    )

    assert command == [
        sys.executable,
        "-m",
        "scripts.run_kiosk_worker",
        "--poll-interval-seconds",
        "1.5",
        "--stale-running-seconds",
        "600",
        "--log-level",
        "DEBUG",
    ]


def test_build_local_visual_engine_service_command_uses_model_python() -> None:
    command = build_local_visual_engine_service_command(
        python_executable="/workspace/tryon-models/venvs/leffa/bin/python",
        host="127.0.0.1",
        port=8091,
        log_level="INFO",
    )

    assert command == [
        "/workspace/tryon-models/venvs/leffa/bin/python",
        "-m",
        "scripts.run_local_visual_engine_service",
        "--host",
        "127.0.0.1",
        "--port",
        "8091",
        "--log-level",
        "INFO",
    ]


def test_build_ollama_command_starts_server() -> None:
    assert build_ollama_command(ollama_command="ollama") == ["ollama", "serve"]
