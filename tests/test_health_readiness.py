from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import health


def test_readiness_endpoint_reports_ready_for_local_kiosk_dependencies(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(health, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(health.httpx, "get", _ollama_tags_response)
    client = _client()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["storage"]["status"] == "ready"
    assert payload["checks"]["garment_registry"]["status"] == "ready"
    assert payload["checks"]["size_chart_registry"]["status"] == "ready"
    assert payload["checks"]["job_queue"]["status"] == "ready"
    assert payload["checks"]["ollama_analyzer_config"]["status"] == "ready"
    assert payload["checks"]["visual_preview_provider"]["status"] == "ready"
    assert payload["checks"]["visual_preview_provider"]["details"]["provider"] == (
        "disabled"
    )
    assert (tmp_path / "garments" / "garments.sqlite3").exists()
    assert (tmp_path / "size_charts" / "size_charts.sqlite3").exists()


def test_readiness_endpoint_returns_503_when_required_config_is_missing(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        health,
        "get_settings",
        lambda: _settings(
            tmp_path,
            kiosk_visual_preview_provider="replicate_qwen",
            replicate_api_token="",
        ),
    )
    monkeypatch.setattr(health.httpx, "get", _ollama_tags_response)
    client = _client()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["visual_preview_provider"]["status"] == "not_ready"
    assert (
        "REPLICATE_API_TOKEN" in payload["checks"]["visual_preview_provider"]["message"]
    )


def test_readiness_endpoint_returns_503_when_ollama_analyzer_model_is_missing(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        health,
        "get_settings",
        lambda: _settings(tmp_path, tryon_analyzer_ollama_model=""),
    )
    client = _client()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    payload = response.json()
    assert payload["checks"]["ollama_analyzer_config"]["status"] == "not_ready"
    assert (
        "TRYON_ANALYZER_OLLAMA_MODEL"
        in payload["checks"]["ollama_analyzer_config"]["message"]
    )


def test_readiness_endpoint_returns_503_when_ollama_model_is_not_installed(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        health,
        "get_settings",
        lambda: _settings(tmp_path, tryon_analyzer_ollama_model="missing-model:latest"),
    )
    monkeypatch.setattr(health.httpx, "get", _ollama_tags_response)
    client = _client()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    payload = response.json()
    check = payload["checks"]["ollama_analyzer_config"]
    assert check["status"] == "not_ready"
    assert "not installed" in check["message"]
    assert check["details"]["available_models"] == ["qwen2.5vl:7b-q4_K_M"]


def test_readiness_endpoint_returns_503_when_ollama_runtime_is_unreachable(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(health, "get_settings", lambda: _settings(tmp_path))

    def raise_connect_error(url: str, timeout: float):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(health.httpx, "get", raise_connect_error)
    client = _client()

    response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    payload = response.json()
    check = payload["checks"]["ollama_analyzer_config"]
    assert check["status"] == "not_ready"
    assert "not reachable" in check["message"]
    assert check["details"]["tags_url"] == "http://127.0.0.1:11434/api/tags"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(health.router)
    return TestClient(app)


def _settings(
    tmp_path: Path,
    *,
    kiosk_visual_preview_provider: str = "disabled",
    replicate_api_token: str = "test-token",
    tryon_analyzer_ollama_model: str = "qwen2.5vl:7b-q4_K_M",
):
    return SimpleNamespace(
        temp_storage_dir=tmp_path,
        job_queue_dir=tmp_path / "jobs",
        ollama_base_url="http://127.0.0.1:11434",
        tryon_analyzer_ollama_model=tryon_analyzer_ollama_model,
        kiosk_visual_preview_provider=kiosk_visual_preview_provider,
        replicate_api_token=replicate_api_token,
        replicate_preview_model="qwen/qwen-image-edit-2511",
        replicate_preview_input_mapping="multi_image_edit",
    )


def _ollama_tags_response(url: str, timeout: float):
    return httpx.Response(
        200,
        json={"models": [{"name": "qwen2.5vl:7b-q4_K_M"}]},
        request=httpx.Request("GET", url),
    )
