from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import kiosk_tryon
from src.modules.kiosk_tryon.garment_registry import GarmentRecord
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
            capture_analysis=None,
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
        if garment_id == "garment:v1:missing":
            raise FileNotFoundError("Garment not found: garment:v1:missing")
        self.session = replace(
            self.session,
            status=(
                "avatar_preview_ready"
                if avatar_preview_cache_key
                else "awaiting_user_capture"
            ),
            garment_id=garment_id,
            avatar_cache_key=avatar_cache_key,
            avatar_preview_cache_key=avatar_preview_cache_key,
        )
        return self.session

    def analyze_user_capture(self, *, session_id):
        self.session = replace(
            self.session,
            status="capture_analysis_passed",
            capture_analysis={
                "passed": True,
                "score": 0.94,
                "issues": [],
                "guidance": [],
                "checks": {
                    "full_body_visible": True,
                    "arms_not_blocking_torso": True,
                },
            },
            updated_at="2026-06-01T00:02:00+00:00",
        )
        return self.session

    def get_session(self, session_id):
        if session_id == "kiosk-session:v1:missing":
            raise FileNotFoundError("Kiosk session not found")
        if session_id == "kiosk-session:v1:ready":
            return replace(
                self.session,
                session_id=session_id,
                status="capture_analysis_passed",
                garment_id="garment:v1:test",
                capture_keys=["front"],
                captures={"front": {"path": "captures/front.png"}},
                capture_analysis={"passed": True},
            )
        return self.session

    def add_user_capture(self, *, session_id, front_image, side_image=None):
        if front_image == b"":
            raise ValueError("front_image must not be empty")
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

    def read_capture_image(self, *, session_id, capture_key):
        if capture_key != "front":
            raise ValueError(f"{capture_key} capture is not available")
        return b"front-image"

    def mark_personalized_tryon_ready(self, *, session_id, personalized_tryon_key):
        self.session = replace(
            self.get_session(session_id),
            status="personalized_tryon_ready",
            personalized_tryon_key=personalized_tryon_key,
        )
        return self.session

    def mark_fit_analysis_ready(self, *, session_id, fit_analysis_key):
        self.session = replace(
            self.get_session(session_id),
            status="fit_analysis_ready",
            fit_analysis_key=fit_analysis_key,
        )
        return self.session


class FakeGarmentRegistry:
    def __init__(self) -> None:
        self.records = [
            GarmentRecord(
                garment_id="garment:v1:test",
                name="Mint jersey",
                category="tops",
                garment_type="jersey",
                storage_provider="local",
                storage_uri="data/garments/images/garment-v1-test.png",
                image_sha256="abc123",
                mime_type="image/png",
                size_bytes=12,
                original_filename="jersey.png",
                created_at="2026-06-01T00:00:00+00:00",
                updated_at="2026-06-01T00:00:00+00:00",
            )
        ]

    def create_garment(
        self,
        *,
        image_bytes,
        category,
        name=None,
        garment_type=None,
        original_filename=None,
        max_size_bytes=None,
    ):
        if image_bytes == b"invalid":
            raise ValueError("garment image file must be a valid PNG, JPEG, or WEBP")
        record = replace(
            self.records[0],
            name=name,
            category=category,
            garment_type=garment_type,
            original_filename=original_filename,
            size_bytes=len(image_bytes),
        )
        self.records = [record]
        return record

    def list_garments(self, *, limit=100):
        return self.records[:limit]

    def get_garment(self, garment_id):
        for record in self.records:
            if record.garment_id == garment_id:
                return record
        return None

    def read_image(self, garment_id):
        if self.get_garment(garment_id) is None:
            raise FileNotFoundError(f"Garment not found: {garment_id}")
        return b"garment-image"


class FakeKioskVisualTryOnService:
    def generate_tryon(
        self,
        *,
        session_id,
        garment_id,
        user_image,
        garment_image,
        garment_category,
        garment_type=None,
        use_multimodal_analysis=True,
        size="1024x1024",
    ):
        assert session_id == "kiosk-session:v1:ready"
        assert garment_id == "garment:v1:test"
        assert user_image == b"front-image"
        assert garment_image == b"garment-image"
        assert garment_category == "tops"
        return {
            "generated_image": "generated-b64",
            "personalized_tryon_key": "kiosk-tryon:v1:test",
            "personalized_tryon_path": "data/kiosk_tryons/images/test.png",
            "metadata_path": "data/kiosk_tryons/metadata/test.json",
            "cache_hit": False,
            "model": "qwen/qwen-image-edit-2511",
            "prompt_version": "qwen-tryon-v1",
            "input_mapping": "multi_image_edit",
            "generation_time_seconds": 1.25,
            "multimodal_analysis_applied": use_multimodal_analysis,
            "tryon_intent": {"garment_region": "upper_body"},
            "analyzer_model": "qwen2.5vl:7b",
            "analyzer_prompt_version": "avatar-tryon-analyzer-v1",
            "warnings": [],
        }


class FakeKioskFitIntelligenceService:
    def generate_tryon(self):
        raise AssertionError("fit service should not generate images")

    def analyze_fit(
        self,
        *,
        session_id,
        garment_id,
        garment_category,
        garment_type,
        capture_analysis,
        front_image,
        side_image=None,
        garment_image=None,
        size_chart=None,
        preferred_fit="regular",
        body_measurements=None,
        use_ai_analysis=True,
    ):
        assert session_id == "kiosk-session:v1:ready"
        assert garment_id == "garment:v1:test"
        assert garment_category == "tops"
        assert garment_type == "jersey"
        assert capture_analysis == {"passed": True}
        assert front_image == b"front-image"
        assert side_image is None
        assert garment_image == b"garment-image"
        assert preferred_fit == "regular"
        assert size_chart == [{"size": "M", "chest_cm": 96.0}]
        assert body_measurements == {"chest_cm": 90.0}
        assert use_ai_analysis is False
        return {
            "fit_analysis_key": "kiosk-fit:v1:test",
            "fit_analysis_path": "data/kiosk_fit/metadata/test.json",
            "cache_hit": False,
            "engine_version": "kiosk-fit-intelligence-hybrid-v2",
            "measurement_estimate": {"status": "provided_measurements"},
            "ai_fit_analysis": {"status": "disabled"},
            "fit_assessment": {"status": "scored"},
            "size_scores": [
                {
                    "size": "M",
                    "score": 0.75,
                    "risks": [],
                    "reason": "chest_cm: garment 96cm vs body 90cm",
                    "source": "deterministic_scorer",
                }
            ],
            "size_recommendation": {
                "status": "recommended",
                "recommended_size": "M",
                "source": "deterministic_scorer",
            },
            "fit_report": {
                "status": "recommended",
                "recommended_size": "M",
                "region_assessments": {"chest_cm": {"fit_label": "aligned"}},
            },
            "confidence_score": 0.55,
            "warnings": ["AI fit analysis is advisory only"],
        }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(kiosk_tryon.router)
    app.dependency_overrides[kiosk_tryon.get_kiosk_tryon_service] = (
        lambda: FakeKioskTryOnService()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_garment_registry] = (
        lambda: FakeGarmentRegistry()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_visual_tryon_service] = (
        lambda: FakeKioskVisualTryOnService()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_fit_intelligence_service] = (
        lambda: FakeKioskFitIntelligenceService()
    )
    return TestClient(app)


def test_upload_kiosk_garment_endpoint_accepts_multipart_file():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={
            "category": "tops",
            "name": "Mint jersey",
            "garment_type": "jersey",
        },
        files={"file": ("jersey.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["garment"]["garment_id"] == "garment:v1:test"
    assert payload["garment"]["name"] == "Mint jersey"
    assert payload["garment"]["category"] == "tops"
    assert payload["garment"]["garment_type"] == "jersey"
    assert payload["garment"]["storage_provider"] == "local"
    assert payload["garment"]["storage_uri"].endswith("garment-v1-test.png")
    assert payload["garment"]["original_filename"] == "jersey.png"


def test_upload_kiosk_garment_endpoint_returns_422_for_invalid_image():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={"category": "tops"},
        files={"file": ("bad.txt", b"invalid", "text/plain")},
    )

    assert response.status_code == 422
    assert "valid PNG, JPEG, or WEBP" in response.json()["detail"]


def test_list_kiosk_garments_endpoint_returns_registered_garments():
    client = _client()

    response = client.get("/api/v1/kiosk/garments")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["garments"][0]["garment_id"] == "garment:v1:test"


def test_get_kiosk_garment_endpoint_returns_registered_garment():
    client = _client()

    response = client.get("/api/v1/kiosk/garments/garment:v1:test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["garment"]["garment_id"] == "garment:v1:test"


def test_get_kiosk_garment_endpoint_returns_404_for_missing_garment():
    client = _client()

    response = client.get("/api/v1/kiosk/garments/garment:v1:missing")

    assert response.status_code == 404
    assert "Garment not found" in response.json()["detail"]


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


def test_create_kiosk_session_endpoint_allows_direct_user_capture_flow():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions",
        json={
            "garment_id": "garment-001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "awaiting_user_capture"
    assert payload["garment_id"] == "garment-001"
    assert payload["avatar_cache_key"] is None
    assert payload["avatar_preview_cache_key"] is None


def test_create_kiosk_session_endpoint_returns_404_for_missing_garment():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions",
        json={"garment_id": "garment:v1:missing"},
    )

    assert response.status_code == 404
    assert "Garment not found" in response.json()["detail"]


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
        files={
            "front_image": ("front.png", b"front-image", "image/png"),
            "side_image": ("side.png", b"side-image", "image/png"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "user_captured"
    assert payload["capture_keys"] == ["front", "side"]
    assert payload["captures"]["front"]["path"].endswith("-front.png")
    assert payload["captures"]["side"]["path"].endswith("-side.png")


def test_analyze_user_capture_endpoint_returns_capture_analysis():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/captures/analyze"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "capture_analysis_passed"
    assert payload["capture_analysis"] == {
        "passed": True,
        "score": 0.94,
        "issues": [],
        "guidance": [],
        "checks": {
            "full_body_visible": True,
            "arms_not_blocking_torso": True,
        },
    }


def test_get_kiosk_session_endpoint_returns_404_for_missing_session():
    client = _client()

    response = client.get("/api/v1/kiosk/sessions/kiosk-session:v1:missing")

    assert response.status_code == 404
    assert "Kiosk session not found" in response.json()["detail"]


def test_add_user_capture_endpoint_returns_422_for_empty_image():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/captures",
        files={"front_image": ("front.png", b"", "image/png")},
    )

    assert response.status_code == 422
    assert "front_image must not be empty" in response.json()["detail"]


def test_generate_visual_preview_endpoint_updates_session():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:ready/visual-preview"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["generated_image"] == "generated-b64"
    assert payload["personalized_tryon_key"] == "kiosk-tryon:v1:test"
    assert payload["session"]["status"] == "personalized_tryon_ready"
    assert payload["session"]["personalized_tryon_key"] == "kiosk-tryon:v1:test"
    assert payload["multimodal_analysis_applied"] is True


def test_generate_visual_preview_endpoint_requires_passed_capture_analysis():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/visual-preview"
    )

    assert response.status_code == 422
    assert "capture analysis must pass" in response.json()["detail"]


def test_legacy_try_on_endpoint_remains_compatible_alias():
    client = _client()

    response = client.post("/api/v1/kiosk/sessions/kiosk-session:v1:ready/try-on")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["personalized_tryon_key"] == "kiosk-tryon:v1:test"


def test_analyze_fit_endpoint_updates_session_with_fit_key():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:ready/fit/analyze",
        json={
            "preferred_fit": "regular",
            "body_measurements": {"chest_cm": 90},
            "use_ai_analysis": False,
            "size_chart": [{"size": "M", "chest_cm": 96}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["fit_analysis_key"] == "kiosk-fit:v1:test"
    assert payload["session"]["status"] == "fit_analysis_ready"
    assert payload["session"]["fit_analysis_key"] == "kiosk-fit:v1:test"
    assert payload["measurement_estimate"]["status"] == "provided_measurements"
    assert payload["ai_fit_analysis"]["status"] == "disabled"
    assert payload["size_scores"][0]["size"] == "M"
    assert payload["size_recommendation"]["status"] == "recommended"
    assert payload["fit_report"]["recommended_size"] == "M"


def test_analyze_fit_endpoint_requires_passed_capture_analysis():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/fit/analyze",
        json={"preferred_fit": "regular"},
    )

    assert response.status_code == 422
    assert "capture analysis must pass" in response.json()["detail"]
