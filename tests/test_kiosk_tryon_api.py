import base64
from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import kiosk_tryon
from src.modules.kiosk_tryon.service import KioskTryOnSession


class FakeKioskTryOnService:
    def __init__(self) -> None:
        self.session = KioskTryOnSession(
            session_id="kiosk-session:v1:test",
            status="avatar_preview_ready",
            garment_id="garment-001",
            avatar_cache_key="avatar:v1:test",
            avatar_preview_cache_key="avatar-preview:v1:test",
            capture_keys=[],
            captures={},
            personalized_tryon_key=None,
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-01T00:00:00+00:00",
        )

    def create_session(
        self,
        *,
        garment_id,
        avatar_cache_key,
        avatar_preview_cache_key,
    ):
        self.session = replace(
            self.session,
            garment_id=garment_id,
            avatar_cache_key=avatar_cache_key,
            avatar_preview_cache_key=avatar_preview_cache_key,
        )
        return self.session

    def get_session(self, session_id):
        if session_id == "kiosk-session:v1:missing":
            raise FileNotFoundError("Kiosk session not found")
        return self.session

    def add_user_capture(self, *, session_id, front_image, side_image=None):
        if front_image == "not-base64":
            raise ValueError("front_image must be valid base64")
        self.session = replace(
            self.session,
            status="user_captured",
            capture_keys=["front", "side"] if side_image is not None else ["front"],
            captures={
                "front": {"path": "captures/kiosk-session-v1-test-front.png"},
                **(
                    {"side": {"path": "captures/kiosk-session-v1-test-side.png"}}
                    if side_image is not None
                    else {}
                ),
            },
            updated_at="2026-06-01T00:01:00+00:00",
        )
        return self.session


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(kiosk_tryon.router)
    app.dependency_overrides[kiosk_tryon.get_kiosk_tryon_service] = (
        lambda: FakeKioskTryOnService()
    )
    return TestClient(app)


def _image_b64(value: bytes = b"image-bytes") -> str:
    return base64.b64encode(value).decode("utf-8")


def test_create_kiosk_session_endpoint_returns_avatar_preview_context():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions",
        json={
            "garment_id": "garment-001",
            "avatar_cache_key": "avatar:v1:abc",
            "avatar_preview_cache_key": "avatar-preview:v1:def",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["session_id"] == "kiosk-session:v1:test"
    assert payload["status"] == "avatar_preview_ready"
    assert payload["garment_id"] == "garment-001"
    assert payload["avatar_cache_key"] == "avatar:v1:abc"
    assert payload["avatar_preview_cache_key"] == "avatar-preview:v1:def"
    assert payload["capture_keys"] == []
    assert payload["captures"] == {}
    assert payload["personalized_tryon_key"] is None


def test_get_kiosk_session_endpoint_returns_existing_session():
    client = _client()

    response = client.get("/api/v1/kiosk/sessions/kiosk-session:v1:test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["session_id"] == "kiosk-session:v1:test"
    assert payload["status"] == "avatar_preview_ready"


def test_add_user_capture_endpoint_updates_session_status():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/captures",
        json={
            "front_image": _image_b64(b"front-image"),
            "side_image": _image_b64(b"side-image"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "user_captured"
    assert payload["capture_keys"] == ["front", "side"]
    assert payload["captures"]["front"]["path"].endswith("-front.png")
    assert payload["captures"]["side"]["path"].endswith("-side.png")


def test_get_kiosk_session_endpoint_returns_404_for_missing_session():
    client = _client()

    response = client.get("/api/v1/kiosk/sessions/kiosk-session:v1:missing")

    assert response.status_code == 404
    assert "Kiosk session not found" in response.json()["detail"]


def test_add_user_capture_endpoint_returns_422_for_invalid_image():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/captures",
        json={
            "front_image": "not-base64",
        },
    )

    assert response.status_code == 422
    assert "front_image must be valid base64" in response.json()["detail"]
