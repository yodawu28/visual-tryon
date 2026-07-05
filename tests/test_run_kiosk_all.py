import sys
from types import SimpleNamespace

import scripts.run_kiosk_all as run_kiosk_all
from scripts.run_kiosk_all import (
    _env_int,
    build_api_command,
    build_local_visual_engine_service_command,
    build_local_visual_engine_worker_env,
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


def test_env_int_uses_default_for_malformed_value(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_VISUAL_ENGINE_SERVICE_PORT", "abc")

    assert _env_int("LOCAL_VISUAL_ENGINE_SERVICE_PORT", 8091) == 8091


def test_build_local_visual_engine_worker_env_sets_service_mode() -> None:
    env = {
        "LOCAL_VISUAL_ENGINE_MODE": "subprocess",
        "LOCAL_VISUAL_ENGINE_SERVICE_URL": "http://old-service:9000",
        "UNCHANGED": "1",
    }

    worker_env = build_local_visual_engine_worker_env(
        env=env,
        host="127.0.0.1",
        port=8091,
        enabled=True,
    )

    assert worker_env["LOCAL_VISUAL_ENGINE_MODE"] == "service"
    assert worker_env["LOCAL_VISUAL_ENGINE_SERVICE_URL"] == "http://127.0.0.1:8091"
    assert worker_env["UNCHANGED"] == "1"
    assert env["LOCAL_VISUAL_ENGINE_MODE"] == "subprocess"
    assert env["LOCAL_VISUAL_ENGINE_SERVICE_URL"] == "http://old-service:9000"


def test_build_local_visual_engine_worker_env_keeps_env_when_disabled() -> None:
    env = {
        "LOCAL_VISUAL_ENGINE_MODE": "subprocess",
        "LOCAL_VISUAL_ENGINE_SERVICE_URL": "http://old-service:9000",
    }

    assert (
        build_local_visual_engine_worker_env(
            env=env,
            host="127.0.0.1",
            port=8091,
            enabled=False,
        )
        == env
    )


def test_main_passes_service_mode_env_to_worker(monkeypatch) -> None:
    started = []

    monkeypatch.setattr(
        run_kiosk_all,
        "parse_args",
        lambda: SimpleNamespace(
            api_host="0.0.0.0",
            api_port=8080,
            no_worker=False,
            worker_poll_interval_seconds=2.0,
            worker_stale_running_seconds=1800,
            start_ollama=False,
            ollama_command="ollama",
            ollama_base_url="http://127.0.0.1:11434",
            log_level="INFO",
            shutdown_timeout_seconds=15.0,
            start_local_visual_engine_service=True,
            local_visual_engine_service_host="127.0.0.1",
            local_visual_engine_service_port=8099,
            local_visual_engine_python="/workspace/tryon-models/venvs/leffa/bin/python",
        ),
    )

    def fake_start_process(name, command, *, env):
        started.append({"name": name, "command": command, "env": dict(env)})
        return SimpleNamespace(name=name, process=SimpleNamespace())

    monkeypatch.setattr(run_kiosk_all, "_start_process", fake_start_process)
    monkeypatch.setattr(run_kiosk_all, "_wait_for_processes", lambda *_, **__: 0)
    monkeypatch.setattr(run_kiosk_all, "_stop_processes", lambda *_, **__: None)

    assert run_kiosk_all.main() == 0

    service = next(item for item in started if item["name"] == "local-visual-engine")
    worker = next(item for item in started if item["name"] == "worker")
    assert service["env"].get("LOCAL_VISUAL_ENGINE_MODE") is None
    assert worker["env"]["LOCAL_VISUAL_ENGINE_MODE"] == "service"
    assert worker["env"]["LOCAL_VISUAL_ENGINE_SERVICE_URL"] == "http://127.0.0.1:8099"


def test_build_ollama_command_starts_server() -> None:
    assert build_ollama_command(ollama_command="ollama") == ["ollama", "serve"]
