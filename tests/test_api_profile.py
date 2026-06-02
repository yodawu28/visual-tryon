from fastapi import FastAPI

from src.api.router_registry import (
    get_router_specs_for_profile,
    include_routers_for_profile,
)
from src.config.settings import Settings


def test_settings_default_api_profile_is_kiosk():
    settings = Settings(replicate_api_token="test-token")

    assert settings.api_profile == "kiosk"


def test_kiosk_api_profile_exposes_only_kiosk_relevant_routes():
    app = FastAPI()

    include_routers_for_profile(app, "kiosk")

    paths = set(app.openapi()["paths"])
    assert "/api/v1/health" in paths
    assert "/api/v1/avatar-preview/avatars" in paths
    assert "/api/v1/avatar-preview/try-on" in paths
    assert "/api/v1/kiosk/sessions" in paths
    assert "/api/v1/kiosk/sessions/{session_id}/captures" in paths
    assert "/api/v1/kiosk/sessions/{session_id}/captures/analyze" in paths

    assert not any(path.startswith("/api/v1/privacy") for path in paths)
    assert not any(path.startswith("/api/v1/analysis") for path in paths)
    assert not any(path.startswith("/api/v1/generate") for path in paths)
    assert not any(path.startswith("/api/v1/products") for path in paths)
    assert not any(path.startswith("/api/v1/tryon") for path in paths)


def test_kiosk_api_profile_openapi_tags_stay_focused():
    app = FastAPI()

    include_routers_for_profile(app, "kiosk")

    tags = {
        tag
        for path_item in app.openapi()["paths"].values()
        for operation in path_item.values()
        for tag in operation.get("tags", [])
    }
    assert tags == {"health", "avatar-preview", "kiosk-tryon"}


def test_full_api_profile_keeps_legacy_router_specs_available():
    specs = get_router_specs_for_profile("full")

    spec_names = [spec.name for spec in specs]
    assert spec_names == [
        "health",
        "privacy",
        "analysis",
        "generation",
        "manual_generation",
        "products",
        "avatar_preview",
        "kiosk_tryon",
    ]


def test_invalid_api_profile_is_rejected():
    app = FastAPI()

    try:
        include_routers_for_profile(app, "unknown")
    except ValueError as exc:
        assert "Unsupported API_PROFILE" in str(exc)
    else:
        raise AssertionError("Expected invalid API_PROFILE to raise ValueError")
