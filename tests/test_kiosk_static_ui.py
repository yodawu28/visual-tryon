import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_kiosk_ui_is_served_from_fastapi(monkeypatch):
    app = _load_main_app(monkeypatch)
    client = TestClient(app)

    response = client.get("/kiosk/")

    assert response.status_code == 200
    assert "Visual Fitting Room" in response.text


def test_kiosk_ui_static_asset_is_served_from_fastapi(monkeypatch):
    app = _load_main_app(monkeypatch)
    client = TestClient(app)

    response = client.get("/kiosk/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "resolveDefaultApiBase" in response.text


def test_kiosk_ui_mount_preserves_api_routes(monkeypatch):
    app = _load_main_app(monkeypatch)
    paths = {route.path for route in app.routes}

    assert "/api/v1/readiness" in paths
    assert "/kiosk" in paths


def test_kiosk_ui_uses_same_origin_default_for_runpod():
    app_js = Path("ui/kiosk-demo/app.js").read_text("utf-8")

    assert "resolveDefaultApiBase" in app_js
    assert "window.location.origin" in app_js
    assert "127.0.0.1:8080" in app_js


def _load_main_app(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("API_PROFILE", "kiosk")
    monkeypatch.setenv("KIOSK_UI_ENABLED", "true")
    monkeypatch.setenv("KIOSK_UI_PATH", "/kiosk")

    for module_name in ("src.main", "src.config.settings"):
        sys.modules.pop(module_name, None)

    settings_module = importlib.import_module("src.config.settings")
    settings_module._settings = None
    main_module = importlib.import_module("src.main")
    return main_module.app
