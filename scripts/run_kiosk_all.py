"""
Run the kiosk API and local worker in one foreground process.

This is intended for single-node MVP deployments such as a RunPod Pod. It keeps
the API and worker as separate child processes, forwards their logs, and shuts
everything down together on SIGINT/SIGTERM.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]


def build_api_command(*, host: str, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_worker_command(
    *,
    poll_interval_seconds: float,
    stale_running_seconds: int,
    log_level: str,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scripts.run_kiosk_worker",
        "--poll-interval-seconds",
        str(poll_interval_seconds),
        "--stale-running-seconds",
        str(stale_running_seconds),
        "--log-level",
        log_level,
    ]


def build_ollama_command(*, ollama_command: str) -> list[str]:
    return [ollama_command, "serve"]


def build_local_visual_engine_service_command(
    *,
    python_executable: str,
    host: str,
    port: int,
    log_level: str,
) -> list[str]:
    return [
        python_executable,
        "-m",
        "scripts.run_local_visual_engine_service",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        log_level,
    ]


def build_local_visual_engine_worker_env(
    *,
    env: dict[str, str],
    host: str,
    port: int,
    enabled: bool,
) -> dict[str, str]:
    worker_env = dict(env)
    if enabled:
        worker_env["LOCAL_VISUAL_ENGINE_MODE"] = "service"
        worker_env["LOCAL_VISUAL_ENGINE_SERVICE_URL"] = f"http://{host}:{port}"
    return worker_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run kiosk API and worker as one deployable foreground process"
    )
    parser.add_argument(
        "--api-host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="API bind host",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=int(os.getenv("PORT", "8080")),
        help="API bind port",
    )
    parser.add_argument(
        "--no-worker",
        action="store_true",
        help="Run only the API process",
    )
    parser.add_argument(
        "--worker-poll-interval-seconds",
        type=float,
        default=2.0,
        help="Worker sleep interval when no job is available",
    )
    parser.add_argument(
        "--worker-stale-running-seconds",
        type=int,
        default=1800,
        help="Worker stale running job recovery threshold",
    )
    parser.add_argument(
        "--start-ollama",
        action="store_true",
        default=_env_flag("KIOSK_START_OLLAMA"),
        help=(
            "Start `ollama serve` if OLLAMA_BASE_URL is not reachable. Can also "
            "be enabled with KIOSK_START_OLLAMA=true."
        ),
    )
    parser.add_argument(
        "--ollama-command",
        default=os.getenv("OLLAMA_COMMAND", "ollama"),
        help="Ollama executable to use with --start-ollama",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        help="Ollama base URL used to decide whether ollama serve is already up",
    )
    parser.add_argument(
        "--start-local-visual-engine-service",
        action="store_true",
        default=_env_flag("LOCAL_VISUAL_ENGINE_START_SERVICE"),
        help=(
            "Start the local visual engine HTTP service before the worker. Can "
            "also be enabled with LOCAL_VISUAL_ENGINE_START_SERVICE=true."
        ),
    )
    parser.add_argument(
        "--local-visual-engine-service-host",
        default=os.getenv("LOCAL_VISUAL_ENGINE_SERVICE_HOST", "127.0.0.1"),
        help="Local visual engine service bind host",
    )
    parser.add_argument(
        "--local-visual-engine-service-port",
        type=int,
        default=_env_int("LOCAL_VISUAL_ENGINE_SERVICE_PORT", 8091),
        help="Local visual engine service bind port",
    )
    parser.add_argument(
        "--local-visual-engine-python",
        default=os.getenv("LOCAL_LEFFA_PYTHON", sys.executable),
        help="Python executable used to start the local visual engine service",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Worker log level",
    )
    parser.add_argument(
        "--shutdown-timeout-seconds",
        type=float,
        default=15.0,
        help="Seconds to wait before killing child processes on shutdown",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = os.environ.copy()
    env.setdefault("API_PROFILE", "kiosk")
    worker_env = build_local_visual_engine_worker_env(
        env=env,
        host=args.local_visual_engine_service_host,
        port=args.local_visual_engine_service_port,
        enabled=args.start_local_visual_engine_service,
    )

    shutdown_requested = threading.Event()
    processes: list[ManagedProcess] = []

    def request_shutdown(signum: int, _frame: object) -> None:
        print(f"[supervisor] received signal {signum}; shutting down", flush=True)
        shutdown_requested.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    try:
        if args.start_ollama:
            if _ollama_is_reachable(args.ollama_base_url):
                print("[supervisor] ollama is already reachable; not starting it")
            else:
                processes.append(
                    _start_process(
                        "ollama",
                        build_ollama_command(ollama_command=args.ollama_command),
                        env=env,
                    )
                )

        processes.append(
            _start_process(
                "api",
                build_api_command(host=args.api_host, port=args.api_port),
                env=env,
            )
        )
        if args.start_local_visual_engine_service:
            processes.append(
                _start_process(
                    "local-visual-engine",
                    build_local_visual_engine_service_command(
                        python_executable=args.local_visual_engine_python,
                        host=args.local_visual_engine_service_host,
                        port=args.local_visual_engine_service_port,
                        log_level=args.log_level,
                    ),
                    env=env,
                )
            )
        if not args.no_worker:
            processes.append(
                _start_process(
                    "worker",
                    build_worker_command(
                        poll_interval_seconds=args.worker_poll_interval_seconds,
                        stale_running_seconds=args.worker_stale_running_seconds,
                        log_level=args.log_level,
                    ),
                    env=worker_env,
                )
            )

        return _wait_for_processes(
            processes,
            shutdown_requested=shutdown_requested,
            shutdown_timeout_seconds=args.shutdown_timeout_seconds,
        )
    except FileNotFoundError as exc:
        print(f"[supervisor] failed to start process: {exc}", file=sys.stderr)
        return 127
    finally:
        _stop_processes(processes, timeout_seconds=args.shutdown_timeout_seconds)


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _ollama_is_reachable(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _start_process(
    name: str,
    command: Sequence[str],
    *,
    env: dict[str, str],
) -> ManagedProcess:
    print(f"[supervisor] starting {name}: {' '.join(command)}", flush=True)
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    managed = ManagedProcess(name=name, process=process)
    threading.Thread(target=_stream_output, args=(managed,), daemon=True).start()
    return managed


def _stream_output(managed: ManagedProcess) -> None:
    if managed.process.stdout is None:
        return
    for line in managed.process.stdout:
        print(f"[{managed.name}] {line}", end="", flush=True)


def _wait_for_processes(
    processes: Sequence[ManagedProcess],
    *,
    shutdown_requested: threading.Event,
    shutdown_timeout_seconds: float,
) -> int:
    while not shutdown_requested.is_set():
        for managed in processes:
            return_code = managed.process.poll()
            if return_code is not None:
                print(
                    f"[supervisor] {managed.name} exited with code {return_code}",
                    flush=True,
                )
                _stop_processes(processes, timeout_seconds=shutdown_timeout_seconds)
                return return_code
        time.sleep(0.5)

    _stop_processes(processes, timeout_seconds=shutdown_timeout_seconds)
    return 0


def _stop_processes(
    processes: Sequence[ManagedProcess],
    *,
    timeout_seconds: float,
) -> None:
    running = [managed for managed in processes if managed.process.poll() is None]
    for managed in running:
        print(f"[supervisor] stopping {managed.name}", flush=True)
        managed.process.terminate()

    deadline = time.monotonic() + timeout_seconds
    for managed in running:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            managed.process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            print(f"[supervisor] killing {managed.name}", flush=True)
            managed.process.kill()
            managed.process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
