from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator
from urllib.parse import urlparse

from src.modules.local_visual_engine.contracts import GenerateRequest, VisualEngine


logger = logging.getLogger(__name__)


class LocalVisualEngineHTTPServer:
    def __init__(self, *, host: str, port: int, engine: VisualEngine) -> None:
        self.host = host
        self.port = port
        self.engine = engine
        self._generation_lock = threading.Lock()
        self._loaded = False
        self._metadata: dict[str, Any] | None = None
        self._server = ThreadingHTTPServer((host, port), self._build_handler())

    @property
    def server_address(self) -> tuple[str, int]:
        host, port = self._server.server_address
        return str(host), int(port)

    def load_engine(self) -> None:
        started = time.perf_counter()
        metadata = self.engine.load()
        self._metadata = metadata.to_dict()
        self._loaded = True
        logger.info(
            "Loaded local visual engine engine=%s duration_seconds=%.2f",
            metadata.engine,
            time.perf_counter() - started,
        )

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @contextmanager
    def running_in_thread(self, *, load_engine: bool) -> Iterator[str]:
        if load_engine:
            self.load_engine()

        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        host, port = self.server_address
        try:
            yield f"http://{host}:{port}"
        finally:
            self.shutdown()
            thread.join(timeout=2)

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                path = urlparse(self.path).path
                try:
                    if path == "/health":
                        self._write_json(HTTPStatus.OK, {"status": "ok"})
                        return
                    if path == "/ready":
                        self._write_json(
                            HTTPStatus.OK,
                            {
                                "ready": server._loaded and server.engine.is_ready(),
                                "engine_metadata": server._metadata,
                            },
                        )
                        return
                    self._write_json(
                        HTTPStatus.NOT_FOUND,
                        {
                            "success": False,
                            "error": {"message": "Not found"},
                        },
                    )
                except Exception as exc:  # pragma: no cover - defensive boundary
                    self._write_exception(exc)

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                if path != "/v1/generate":
                    self._write_json(
                        HTTPStatus.NOT_FOUND,
                        {
                            "success": False,
                            "error": {"message": "Not found"},
                        },
                    )
                    return

                request_started = time.perf_counter()
                try:
                    payload = self._read_json()
                    request = GenerateRequest.from_dict(payload)
                    loaded_engine = self._loaded_engine_name()
                    if request.engine != loaded_engine:
                        self._write_json(
                            HTTPStatus.CONFLICT,
                            {
                                "success": False,
                                "error": {
                                    "message": (
                                        "Requested engine "
                                        f"{request.engine}; loaded engine "
                                        f"{loaded_engine}"
                                    )
                                },
                            },
                        )
                        return

                    if not server._loaded or not server.engine.is_ready():
                        self._write_json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            {
                                "success": False,
                                "error": {"message": "Engine is not ready"},
                            },
                        )
                        return

                    wait_started = time.perf_counter()
                    with server._generation_lock:
                        generation_started = time.perf_counter()
                        result = server.engine.generate(request).to_dict()

                    result["queue_wait_seconds"] = generation_started - wait_started
                    result["total_time_seconds"] = time.perf_counter() - request_started
                    self._write_json(HTTPStatus.OK, result)
                except Exception as exc:
                    self._write_exception(exc)

            def log_message(self, format: str, *args: Any) -> None:
                logger.info("%s - %s", self.address_string(), format % args)

            def _loaded_engine_name(self) -> str:
                if server._metadata is not None:
                    return str(server._metadata["engine"])
                return server.engine.metadata().engine

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                data = self.rfile.read(length)
                payload = json.loads(data.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object")
                return payload

            def _write_exception(self, exc: Exception) -> None:
                logger.exception("Local visual engine request failed")
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "success": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    },
                )

            def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
