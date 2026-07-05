import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from src.modules.local_visual_engine.contracts import (
    EngineMetadata,
    GenerateRequest,
    GenerateResult,
)
from src.modules.local_visual_engine.service import LocalVisualEngineHTTPServer


@dataclass
class FakeEngine:
    loaded: bool = False
    calls: int = 0
    call_windows: list[tuple[float, float]] = field(default_factory=list)

    def load(self) -> EngineMetadata:
        self.loaded = True
        return self.metadata()

    def is_ready(self) -> bool:
        return self.loaded

    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            engine="fake",
            implementation="FakeEngine",
            model_repo_id="fake/model",
            checkpoint_dir="/tmp/fake-ckpts",
            device="cpu",
            dtype="float32",
            model_type="fake",
        )

    def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls += 1
        started = time.perf_counter()
        time.sleep(0.1)
        finished = time.perf_counter()
        self.call_windows.append((started, finished))
        return GenerateResult(
            success=True,
            engine="fake",
            output=request.output,
            report=request.report,
            artifacts={"mask_output": request.output.replace(".png", "-mask.png")},
            generation_time_seconds=finished - started,
            engine_metadata=self.metadata().to_dict(),
        )


class MetadataUnavailableUntilLoadEngine(FakeEngine):
    def metadata(self) -> EngineMetadata:
        if not self.loaded:
            raise AssertionError("metadata should not be called before load")
        return super().metadata()


def test_health_and_ready_endpoints_reflect_load_state():
    engine = FakeEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)

    with server.running_in_thread(load_engine=False) as base_url:
        assert _get_json(f"{base_url}/health") == {"status": "ok"}
        assert _get_json(f"{base_url}/ready")["ready"] is False

    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)
    with server.running_in_thread(load_engine=True) as base_url:
        ready = _get_json(f"{base_url}/ready")

    assert ready["ready"] is True
    assert ready["engine_metadata"]["engine"] == "fake"
    assert ready["engine_metadata"]["implementation"] == "FakeEngine"


def test_generate_endpoint_calls_engine_and_returns_json():
    engine = FakeEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)

    with server.running_in_thread(load_engine=True) as base_url:
        result = _post_json(f"{base_url}/v1/generate", _generate_payload())

    assert result["success"] is True
    assert result["engine"] == "fake"
    assert result["output"] == "/tmp/out.png"
    assert result["report"] == "/tmp/report.json"
    assert result["artifacts"]["mask_output"] == "/tmp/out-mask.png"
    assert result["engine_metadata"]["engine"] == "fake"
    assert result["queue_wait_seconds"] >= 0
    assert result["total_time_seconds"] >= result["generation_time_seconds"]
    assert engine.calls == 1


def test_generate_endpoint_returns_not_ready_before_metadata_lookup():
    engine = MetadataUnavailableUntilLoadEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)

    with server.running_in_thread(load_engine=False) as base_url:
        response = _post_json_error(f"{base_url}/v1/generate", _generate_payload())

    assert response.code == 503
    assert response.payload["error"]["type"] == "EngineNotReady"
    assert engine.calls == 0


def test_generate_endpoint_rejects_missing_required_field():
    engine = FakeEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)
    payload = _generate_payload()
    payload.pop("garment_image")

    with server.running_in_thread(load_engine=True) as base_url:
        response = _post_json_error(f"{base_url}/v1/generate", payload)

    assert response.code == 400
    assert response.payload["success"] is False
    assert response.payload["error"]["type"] == "InvalidRequest"
    assert "garment_image" in response.payload["error"]["message"]
    assert engine.calls == 0


def test_generate_endpoint_rejects_non_object_json_body():
    engine = FakeEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)

    with server.running_in_thread(load_engine=True) as base_url:
        response = _post_json_error(f"{base_url}/v1/generate", ["not", "an", "object"])

    assert response.code == 400
    assert response.payload["success"] is False
    assert response.payload["error"]["type"] == "InvalidRequest"
    assert engine.calls == 0


def test_generate_endpoint_rejects_wrong_engine():
    engine = FakeEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)

    payload = _generate_payload(engine="leffa")
    with server.running_in_thread(load_engine=True) as base_url:
        response = _post_json_error(f"{base_url}/v1/generate", payload)

    assert response.code == 409
    assert response.payload["success"] is False
    assert "loaded engine fake" in response.payload["error"]["message"]
    assert engine.calls == 0


def test_generate_endpoint_serializes_requests():
    engine = FakeEngine()
    server = LocalVisualEngineHTTPServer(host="127.0.0.1", port=0, engine=engine)

    with server.running_in_thread(load_engine=True) as base_url:
        results: list[dict] = []
        errors: list[BaseException] = []
        lock = threading.Lock()
        barrier = threading.Barrier(3)

        def call(index: int) -> None:
            try:
                barrier.wait(timeout=2)
                result = _post_json(
                    f"{base_url}/v1/generate",
                    _generate_payload(
                        person_image=f"/tmp/person-{index}.png",
                        garment_image=f"/tmp/garment-{index}.png",
                        output=f"/tmp/out-{index}.png",
                        report=f"/tmp/report-{index}.json",
                    ),
                )
                with lock:
                    results.append(result)
            except BaseException as exc:  # pragma: no cover - re-raised below
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=call, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    assert engine.calls == 2
    assert len(engine.call_windows) == 2
    first, second = sorted(engine.call_windows)
    assert first[1] <= second[0]
    assert any(result["queue_wait_seconds"] >= 0.05 for result in results)


@dataclass(frozen=True)
class ErrorResponse:
    code: int
    payload: dict


def _generate_payload(**overrides: object) -> dict:
    payload = {
        "engine": "fake",
        "person_image": "/tmp/person.png",
        "garment_image": "/tmp/garment.png",
        "output": "/tmp/out.png",
        "report": "/tmp/report.json",
        "garment_type": "upper_body",
        "size": "768x1024",
        "steps": 30,
        "guidance_scale": 2.5,
        "seed": 42,
        "ref_acceleration": False,
        "repaint": False,
        "preprocess_garment": False,
    }
    payload.update(overrides)
    return payload


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: object) -> dict:
    with urllib.request.urlopen(_json_request(url, payload), timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json_error(url: str, payload: object) -> ErrorResponse:
    try:
        _post_json(url, payload)
    except urllib.error.HTTPError as exc:
        return ErrorResponse(
            code=exc.code,
            payload=json.loads(exc.read().decode("utf-8")),
        )
    raise AssertionError("Expected request to fail")


def _json_request(url: str, payload: object) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
