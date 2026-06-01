import base64
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import avatar_preview
from src.schemas.requests import AvatarPreviewTryOnRequest


class FakeAvatarPreviewService:
    def generate_avatar(
        self,
        *,
        profile_input,
        garment_region,
        garment_type=None,
        garment_sleeve_length=None,
        avatar_framing=None,
        force_regenerate=False,
    ):
        effective_garment_region = (
            "upper_body"
            if garment_type and garment_type.value == "jersey"
            else garment_region.value
        )
        return {
            "avatar_image": base64.b64encode(b"avatar-image").decode("utf-8"),
            "avatar_cache_key": "avatar:v1:test",
            "avatar_framing": avatar_framing.value if avatar_framing else "full_body",
            "garment_region": effective_garment_region,
            "garment_type": garment_type.value if garment_type else None,
            "garment_sleeve_length": (
                garment_sleeve_length.value if garment_sleeve_length else "unknown"
            ),
            "cache_hit": False,
            "avatar_prompt_version": "avatar-body-profile-v4",
            "avatar_path": Path("data/avatar_cache/avatar-v1-test.png"),
            "metadata_path": Path("data/avatar_cache/avatar-v1-test.json"),
            "metadata": {
                "derived_profile": profile_input.model_dump(mode="json"),
            },
        }

    def try_on_cached_avatar(
        self,
        *,
        avatar_cache_key,
        product_image,
        quality_mode,
        size,
        use_multimodal_analysis=False,
    ):
        if quality_mode.value == "garment_fidelity":
            raise ValueError("avatar preview only supports creative_preview")
        return {
            "generated_image": base64.b64encode(b"preview-image").decode("utf-8"),
            "avatar_cache_key": avatar_cache_key,
            "avatar_framing": "full_body",
            "garment_region": "lower_body",
            "garment_type": "shorts",
            "is_preview": True,
            "quality_mode": quality_mode.value,
            "preview_model": "qwen/qwen-image-edit-2511",
            "preview_prompt_version": "avatar-qwen-multimodal-preview-v1",
            "model_warning": "Creative preview; not exact virtual try-on.",
            "generation_time_seconds": 1.25,
            "preview_cache_key": "avatar-preview:v1:test",
            "preview_cache_hit": False,
            "preview_path": Path("data/avatar_cache/avatar-preview-v1-test.png"),
            "preview_metadata_path": Path(
                "data/avatar_cache/avatar-preview-v1-test.json"
            ),
            "product_scope": "avatar_creative_preview",
            "baseline_scope": "upper_body",
            "multimodal_analysis_applied": use_multimodal_analysis,
            "tryon_intent": (
                {
                    "garment_region": "upper_body",
                    "garment_type": "jersey",
                    "sleeve_length": "short_sleeve",
                }
                if use_multimodal_analysis
                else None
            ),
            "analyzer_model": "qwen2.5vl:7b" if use_multimodal_analysis else None,
            "analyzer_prompt_version": (
                "avatar-tryon-analyzer-v1" if use_multimodal_analysis else None
            ),
        }

    def get_cached_avatar(self, avatar_cache_key):
        return {
            "avatar_image": base64.b64encode(b"avatar-image").decode("utf-8"),
            "avatar_cache_key": avatar_cache_key,
            "avatar_framing": "full_body",
            "garment_region": "upper_body",
            "garment_type": "jersey",
            "garment_sleeve_length": "short_sleeve",
            "cache_hit": True,
            "avatar_prompt_version": "avatar-body-profile-v4",
            "avatar_path": Path("data/avatar_cache/avatar-v1-test.png"),
            "metadata_path": Path("data/avatar_cache/avatar-v1-test.json"),
            "metadata": {},
        }

    def get_cached_preview(self, preview_cache_key):
        return {
            "generated_image": base64.b64encode(b"preview-image").decode("utf-8"),
            "avatar_cache_key": "avatar:v1:test",
            "avatar_framing": "full_body",
            "garment_region": "upper_body",
            "garment_type": "jersey",
            "is_preview": True,
            "quality_mode": "creative_preview",
            "preview_model": "qwen/qwen-image-edit-2511",
            "preview_prompt_version": "avatar-qwen-multimodal-preview-v1",
            "model_warning": "Creative preview; not exact virtual try-on.",
            "preview_cache_key": preview_cache_key,
            "preview_cache_hit": True,
            "preview_path": Path("data/avatar_cache/avatar-preview-v1-test.png"),
            "preview_metadata_path": Path(
                "data/avatar_cache/avatar-preview-v1-test.json"
            ),
            "product_scope": "avatar_creative_preview",
            "baseline_scope": "upper_body",
            "multimodal_analysis_applied": False,
            "tryon_intent": None,
        }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(avatar_preview.router)
    app.dependency_overrides[avatar_preview.get_avatar_preview_service] = (
        lambda: FakeAvatarPreviewService()
    )
    return TestClient(app)


def _body_profile() -> dict:
    return {
        "input_mode": "basic",
        "basic": {
            "gender_presentation": "male",
            "body_build": "athletic",
            "height_range": "tall",
            "shoulder_width": "broad",
            "fit_preference": "regular",
            "pose": "front_relaxed",
            "skin_tone": "not_specified",
            "age_band": "adult",
        },
    }


def test_generate_avatar_endpoint_returns_cache_metadata():
    client = _client()

    response = client.post(
        "/api/v1/avatar-preview/avatars",
        json={
            "body_profile": _body_profile(),
            "garment_type": "jersey",
            "garment_sleeve_length": "short_sleeve",
            "avatar_framing": "full_body",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["avatar_cache_key"] == "avatar:v1:test"
    assert payload["avatar_framing"] == "full_body"
    assert payload["garment_region"] == "upper_body"
    assert payload["garment_type"] == "jersey"
    assert payload["garment_sleeve_length"] == "short_sleeve"
    assert payload["cache_hit"] is False
    assert payload["avatar_image"]
    assert payload["avatar_path"].endswith("avatar-v1-test.png")


def test_get_cached_avatar_endpoint_returns_cached_avatar_image():
    client = _client()

    response = client.get("/api/v1/avatar-preview/avatars/avatar:v1:test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["avatar_cache_key"] == "avatar:v1:test"
    assert payload["cache_hit"] is True
    assert payload["avatar_image"]
    assert payload["garment_type"] == "jersey"
    assert payload["message"] == "Avatar loaded from cache"


def test_try_on_cached_avatar_endpoint_returns_preview_metadata():
    client = _client()

    response = client.post(
        "/api/v1/avatar-preview/try-on",
        json={
            "avatar_cache_key": "avatar:v1:test",
            "product_image": base64.b64encode(b"product-image").decode("utf-8"),
            "quality_mode": "creative_preview",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["generated_image"]
    assert payload["avatar_cache_key"] == "avatar:v1:test"
    assert payload["avatar_framing"] == "full_body"
    assert payload["garment_region"] == "lower_body"
    assert payload["garment_type"] == "shorts"
    assert payload["quality_mode"] == "creative_preview"
    assert payload["is_preview"] is True
    assert payload["preview_model"] == "qwen/qwen-image-edit-2511"
    assert payload["preview_cache_key"] == "avatar-preview:v1:test"
    assert payload["preview_cache_hit"] is False
    assert payload["preview_path"].endswith("avatar-preview-v1-test.png")
    assert payload["preview_metadata_path"].endswith("avatar-preview-v1-test.json")
    assert payload["product_scope"] == "avatar_creative_preview"
    assert payload["baseline_scope"] == "upper_body"
    assert payload["multimodal_analysis_applied"] is False


def test_try_on_cached_avatar_endpoint_rejects_garment_fidelity_mode():
    client = _client()

    response = client.post(
        "/api/v1/avatar-preview/try-on",
        json={
            "avatar_cache_key": "avatar:v1:test",
            "product_image": base64.b64encode(b"product-image").decode("utf-8"),
            "quality_mode": "garment_fidelity",
        },
    )

    assert response.status_code == 422
    assert "only supports creative_preview" in response.json()["detail"]


def test_try_on_cached_avatar_schema_example_uses_supported_quality_mode():
    schema = AvatarPreviewTryOnRequest.model_json_schema()

    assert schema["example"]["quality_mode"] == "creative_preview"
    quality_mode_description = schema["properties"]["quality_mode"]["description"]
    assert "only supports creative_preview" in quality_mode_description
    assert "IDM-VTON" not in quality_mode_description


def test_get_cached_preview_endpoint_returns_cached_preview_image():
    client = _client()

    response = client.get(
        "/api/v1/avatar-preview/previews/avatar-preview:v1:test",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["generated_image"]
    assert payload["avatar_cache_key"] == "avatar:v1:test"
    assert payload["preview_cache_key"] == "avatar-preview:v1:test"
    assert payload["preview_cache_hit"] is True
    assert payload["preview_path"].endswith("avatar-preview-v1-test.png")
    assert payload["preview_metadata_path"].endswith("avatar-preview-v1-test.json")
    assert payload["product_scope"] == "avatar_creative_preview"
    assert payload["baseline_scope"] == "upper_body"
    assert payload["message"] == "Avatar preview loaded from cache"


def test_try_on_cached_avatar_endpoint_can_return_multimodal_metadata():
    client = _client()

    response = client.post(
        "/api/v1/avatar-preview/try-on",
        json={
            "avatar_cache_key": "avatar:v1:test",
            "product_image": base64.b64encode(b"product-image").decode("utf-8"),
            "quality_mode": "creative_preview",
            "use_multimodal_analysis": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["multimodal_analysis_applied"] is True
    assert payload["tryon_intent"]["sleeve_length"] == "short_sleeve"
    assert payload["analyzer_model"] == "qwen2.5vl:7b"
    assert payload["analyzer_prompt_version"] == "avatar-tryon-analyzer-v1"


def test_avatar_preview_service_factory_uses_qwen_preview_generator(monkeypatch):
    class FakeAvatarGenerator:
        pass

    class FakeQwenPreviewGenerator:
        pass

    class FakeAnalyzer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(
        avatar_preview,
        "ReplicateSyntheticAvatarGenerator",
        FakeAvatarGenerator,
    )
    monkeypatch.setattr(
        avatar_preview,
        "ReplicateAvatarPreviewGenerator",
        FakeQwenPreviewGenerator,
    )
    monkeypatch.setattr(avatar_preview, "OllamaTryOnAnalyzer", FakeAnalyzer)
    avatar_preview.get_avatar_preview_service.cache_clear()

    try:
        service = avatar_preview.get_avatar_preview_service()
    finally:
        avatar_preview.get_avatar_preview_service.cache_clear()

    assert isinstance(service.preview_generator, FakeQwenPreviewGenerator)
    assert not hasattr(service, "fidelity_generator")
    assert not hasattr(avatar_preview, "ReplicateIdmVtonGenerator")


def test_avatar_preview_service_factory_can_use_local_command_avatar_generator(
    monkeypatch,
):
    class FakeReplicateAvatarGenerator:
        pass

    class FakeLocalAvatarGenerator:
        def __init__(self):
            self.source = "local"

    class FakeQwenPreviewGenerator:
        pass

    class FakeAnalyzer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(
        avatar_preview,
        "ReplicateSyntheticAvatarGenerator",
        FakeReplicateAvatarGenerator,
    )
    monkeypatch.setattr(
        avatar_preview,
        "LocalCommandAvatarGenerator",
        FakeLocalAvatarGenerator,
    )
    monkeypatch.setattr(
        avatar_preview,
        "ReplicateAvatarPreviewGenerator",
        FakeQwenPreviewGenerator,
    )
    monkeypatch.setattr(avatar_preview, "OllamaTryOnAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        avatar_preview,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "avatar_generator_mode": "local_command",
                "tryon_analyzer_ollama_model": "qwen2.5vl:7b",
                "ollama_base_url": "http://127.0.0.1:11434",
                "tryon_analyzer_timeout": 300,
                "temp_storage_dir": Path("data"),
            },
        )(),
    )
    avatar_preview.get_avatar_preview_service.cache_clear()

    try:
        service = avatar_preview.get_avatar_preview_service()
    finally:
        avatar_preview.get_avatar_preview_service.cache_clear()

    assert isinstance(service.avatar_generator, FakeLocalAvatarGenerator)
    assert isinstance(service.preview_generator, FakeQwenPreviewGenerator)
