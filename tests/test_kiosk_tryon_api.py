from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import kiosk_tryon
from src.modules.kiosk_tryon.garment_registry import GarmentRecord
from src.modules.kiosk_tryon.service import KioskTryOnSession
from src.modules.kiosk_tryon.size_chart_registry import SizeChartRecord


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
        if session_id == "kiosk-session:v1:fit-ready":
            return replace(
                self.session,
                session_id=session_id,
                status="fit_analysis_ready",
                garment_id="garment:v1:test",
                capture_keys=["front"],
                captures={"front": {"path": "captures/front.png"}},
                capture_analysis={"passed": True},
                fit_analysis_key="kiosk-fit:v1:test",
            )
        return self.session

    def add_user_capture(
        self,
        *,
        session_id,
        front_image,
        side_image=None,
        capture_source=None,
        capture_metadata=None,
    ):
        if front_image == b"":
            raise ValueError("front_image must not be empty")
        source_payload = {"source": capture_source} if capture_source else {}
        metadata_payload = (
            {"metadata": capture_metadata.get("front")}
            if isinstance(capture_metadata, dict) and capture_metadata.get("front")
            else {}
        )
        self.session = replace(
            self.session,
            status="user_captured",
            capture_keys=["front", "side"] if side_image is not None else ["front"],
            captures={
                "front": {
                    "path": "captures/kiosk-session-v1-test-front.png",
                    **source_payload,
                    **metadata_payload,
                },
                **(
                    {
                        "side": {
                            "path": "captures/kiosk-session-v1-test-side.png",
                            **source_payload,
                        }
                    }
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
                size_chart_id="size-chart:v1:test",
                size_chart=[],
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
        size_chart_id=None,
        size_chart=None,
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
            size_chart_id=size_chart_id,
            size_chart=size_chart or [],
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


class FakeKioskSizeChartRegistry:
    def __init__(self) -> None:
        self.records = [
            SizeChartRecord(
                size_chart_id="size-chart:v1:test",
                name="VN tops",
                country_code="VN",
                region="Vietnam",
                category="tops",
                garment_type="jersey",
                source_type="generic_reference",
                source_url=None,
                last_verified_at=None,
                size_chart=[{"size": "M", "chest_cm": 96.0}],
                notes=None,
                created_at="2026-06-01T00:00:00+00:00",
                updated_at="2026-06-01T00:00:00+00:00",
            )
        ]

    def create_size_chart(
        self,
        *,
        name,
        country_code,
        category,
        size_chart,
        region=None,
        garment_type=None,
        source_type=None,
        source_url=None,
        last_verified_at=None,
        notes=None,
    ):
        if not size_chart:
            raise ValueError("size_chart must include at least one size row")
        record = SizeChartRecord(
            size_chart_id="size-chart:v1:new",
            name=name,
            country_code=country_code.upper(),
            region=region,
            category=category,
            garment_type=garment_type,
            source_type=source_type,
            source_url=source_url,
            last_verified_at=last_verified_at,
            size_chart=size_chart,
            notes=notes,
            created_at="2026-06-01T00:00:00+00:00",
            updated_at="2026-06-01T00:00:00+00:00",
        )
        self.records = [record]
        return record

    def get_size_chart(self, size_chart_id):
        if size_chart_id == "size-chart:v1:missing":
            return None
        return next(
            (
                record
                for record in self.records
                if record.size_chart_id == size_chart_id
            ),
            None,
        )

    def list_size_charts(self, *, country_code=None, category=None, limit=100):
        records = self.records
        if country_code:
            records = [
                record
                for record in records
                if record.country_code == country_code.upper()
            ]
        if category:
            records = [record for record in records if record.category == category]
        return records[:limit]


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

    def get_generated_image_path(self, personalized_tryon_key):
        if personalized_tryon_key == "kiosk-tryon:v1:missing":
            raise FileNotFoundError(
                "Kiosk visual preview image not found: kiosk-tryon:v1:missing"
            )
        if not personalized_tryon_key.startswith("kiosk-tryon:v1:"):
            raise ValueError("personalized_tryon_key is not a kiosk try-on key")
        return Path(__file__)


class FakeKioskFitIntelligenceService:
    def generate_tryon(self):
        raise AssertionError("fit service should not generate images")

    def get_analysis(self, fit_analysis_key):
        assert fit_analysis_key == "kiosk-fit:v1:test"
        return self._fit_payload(cache_hit=True)

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
        assert body_measurements == {"height_cm": 178.0, "weight_kg": 74.0}
        assert use_ai_analysis is False
        return self._fit_payload(cache_hit=False)

    def _fit_payload(self, *, cache_hit):
        return {
            "fit_analysis_key": "kiosk-fit:v1:test",
            "fit_analysis_path": "data/kiosk_fit/metadata/test.json",
            "cache_hit": cache_hit,
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


class FakeKioskJobService:
    def create_job(
        self,
        *,
        queue_name,
        job_type,
        payload,
        max_attempts=1,
    ):
        assert queue_name == "gpu.visual_preview"
        assert job_type == "kiosk_visual_preview"
        assert payload == {
            "session_id": "kiosk-session:v1:ready",
            "garment_id": "garment:v1:test",
            "garment_category": "tops",
            "garment_type": "jersey",
            "capture_keys": ["front"],
            "use_multimodal_analysis": False,
            "size": "1024x1024",
        }
        assert max_attempts == 2
        return self._job_payload(status="queued")

    def get_job(self, job_id):
        if job_id == "job:v1:missing":
            raise FileNotFoundError("Job not found: job:v1:missing")
        assert job_id == "job:v1:test"
        return self._job_payload(status="queued")

    def _job_payload(self, *, status):
        return {
            "job_id": "job:v1:test",
            "queue_name": "gpu.visual_preview",
            "job_type": "kiosk_visual_preview",
            "status": status,
            "payload": {
                "session_id": "kiosk-session:v1:ready",
                "garment_id": "garment:v1:test",
                "garment_category": "tops",
                "garment_type": "jersey",
                "capture_keys": ["front"],
                "use_multimodal_analysis": False,
                "size": "1024x1024",
            },
            "result": None,
            "error": None,
            "attempts": 0,
            "max_attempts": 2,
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "started_at": None,
            "finished_at": None,
        }


def _client(*, enable_visual_preview: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(kiosk_tryon.router)
    app.dependency_overrides[kiosk_tryon.get_kiosk_tryon_service] = (
        lambda: FakeKioskTryOnService()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_garment_registry] = (
        lambda: FakeGarmentRegistry()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_size_chart_registry] = (
        lambda: FakeKioskSizeChartRegistry()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_visual_tryon_service] = (
        lambda: FakeKioskVisualTryOnService()
    )
    if enable_visual_preview:
        app.dependency_overrides[kiosk_tryon.require_kiosk_visual_preview_enabled] = (
            lambda: None
        )
    app.dependency_overrides[kiosk_tryon.get_kiosk_fit_intelligence_service] = (
        lambda: FakeKioskFitIntelligenceService()
    )
    app.dependency_overrides[kiosk_tryon.get_kiosk_job_service] = (
        lambda: FakeKioskJobService()
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
    assert payload["garment"]["size_chart"] == []


def test_upload_kiosk_garment_endpoint_accepts_size_chart_json():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={
            "category": "tops",
            "garment_type": "jersey",
            "size_chart_json": '[{"size":"M","chest_cm":96}]',
        },
        files={"file": ("jersey.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["garment"]["size_chart"] == [{"size": "M", "chest_cm": 96.0}]


def test_upload_kiosk_garment_endpoint_accepts_size_chart_id():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={
            "category": "tops",
            "garment_type": "jersey",
            "size_chart_id": "size-chart:v1:test",
        },
        files={"file": ("jersey.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["garment"]["size_chart_id"] == "size-chart:v1:test"


def test_upload_kiosk_garment_endpoint_returns_404_for_missing_size_chart_id():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={"category": "tops", "size_chart_id": "size-chart:v1:missing"},
        files={"file": ("jersey.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 404
    assert "Size chart not found" in response.json()["detail"]


def test_upload_kiosk_garment_endpoint_returns_422_for_invalid_image():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={"category": "tops"},
        files={"file": ("bad.txt", b"invalid", "text/plain")},
    )

    assert response.status_code == 422
    assert "valid PNG, JPEG, or WEBP" in response.json()["detail"]


def test_upload_kiosk_garment_endpoint_returns_422_for_invalid_size_chart_json():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/garments",
        data={"category": "tops", "size_chart_json": '{"size":"M"}'},
        files={"file": ("jersey.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 422
    assert "size_chart_json must be a JSON array" in response.json()["detail"]


def test_create_kiosk_size_chart_endpoint_returns_catalog_record():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/size-charts",
        json={
            "name": "VN tops",
            "country_code": "VN",
            "region": "Vietnam",
            "category": "tops",
            "garment_type": "jersey",
            "source_type": "generic_reference",
            "source_url": "https://example.com/size-chart",
            "last_verified_at": "2026-06-04",
            "size_chart": [{"size": "M", "chest_cm": 96}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["size_chart"]["size_chart_id"] == "size-chart:v1:new"
    assert payload["size_chart"]["country_code"] == "VN"
    assert payload["size_chart"]["source_type"] == "generic_reference"
    assert payload["size_chart"]["source_url"] == "https://example.com/size-chart"
    assert payload["size_chart"]["last_verified_at"] == "2026-06-04"
    assert payload["size_chart"]["size_chart"] == [{"size": "M", "chest_cm": 96.0}]


def test_list_kiosk_size_charts_endpoint_filters_catalog():
    client = _client()

    response = client.get("/api/v1/kiosk/size-charts?country_code=VN&category=tops")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["size_charts"][0]["size_chart_id"] == "size-chart:v1:test"


def test_get_kiosk_size_chart_endpoint_returns_catalog_record():
    client = _client()

    response = client.get("/api/v1/kiosk/size-charts/size-chart:v1:test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["size_chart"]["name"] == "VN tops"


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


def test_enqueue_visual_preview_job_endpoint_returns_queued_job():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:ready/visual-preview/jobs",
        json={
            "use_multimodal_analysis": False,
            "size": "1024x1024",
            "max_attempts": 2,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["success"] is True
    assert payload["job_id"] == "job:v1:test"
    assert payload["queue_name"] == "gpu.visual_preview"
    assert payload["job_type"] == "kiosk_visual_preview"
    assert payload["status"] == "queued"
    assert payload["payload"]["session_id"] == "kiosk-session:v1:ready"
    assert payload["payload"]["garment_id"] == "garment:v1:test"
    assert payload["message"] == "Kiosk visual preview job queued"


def test_enqueue_visual_preview_job_returns_503_when_provider_is_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        kiosk_tryon,
        "get_settings",
        lambda: SimpleNamespace(kiosk_visual_preview_provider="disabled"),
    )
    client = _client(enable_visual_preview=False)

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:ready/visual-preview/jobs",
        json={
            "use_multimodal_analysis": False,
            "size": "1024x1024",
            "max_attempts": 2,
        },
    )

    assert response.status_code == 503
    assert "visual preview provider is disabled" in response.json()["detail"]


def test_get_visual_preview_image_endpoint_returns_png():
    client = _client()

    response = client.get(
        "/api/v1/kiosk/visual-previews/kiosk-tryon:v1:test/image"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content


def test_get_visual_preview_image_endpoint_returns_422_for_invalid_key():
    client = _client()

    response = client.get("/api/v1/kiosk/visual-previews/not-a-key/image")

    assert response.status_code == 422
    assert "not a kiosk try-on key" in response.json()["detail"]


def test_get_kiosk_job_endpoint_returns_job_status():
    client = _client()

    response = client.get("/api/v1/kiosk/jobs/job:v1:test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["job_id"] == "job:v1:test"
    assert payload["status"] == "queued"
    assert payload["payload"]["session_id"] == "kiosk-session:v1:ready"
    assert payload["message"] == "Kiosk job loaded"


def test_get_kiosk_job_endpoint_returns_404_for_missing_job():
    client = _client()

    response = client.get("/api/v1/kiosk/jobs/job:v1:missing")

    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


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
            "body_measurements": {"height_cm": 178, "weight_kg": 74},
            "use_ai_analysis": False,
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


def test_get_fit_analysis_endpoint_loads_cached_session_fit_result():
    client = _client()

    response = client.get(
        "/api/v1/kiosk/sessions/kiosk-session:v1:fit-ready/fit/analysis"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["fit_analysis_key"] == "kiosk-fit:v1:test"
    assert payload["cache_hit"] is True
    assert payload["session"]["status"] == "fit_analysis_ready"
    assert payload["session"]["fit_analysis_key"] == "kiosk-fit:v1:test"
    assert payload["fit_report"]["recommended_size"] == "M"
    assert payload["message"] == "Kiosk fit analysis loaded"


def test_get_fit_analysis_endpoint_returns_404_when_session_has_no_fit_result():
    client = _client()

    response = client.get("/api/v1/kiosk/sessions/kiosk-session:v1:ready/fit/analysis")

    assert response.status_code == 404
    assert "Fit analysis not found for session" in response.json()["detail"]


def test_analyze_fit_endpoint_requires_passed_capture_analysis():
    client = _client()

    response = client.post(
        "/api/v1/kiosk/sessions/kiosk-session:v1:test/fit/analyze",
        json={"preferred_fit": "regular"},
    )

    assert response.status_code == 422
    assert "capture analysis must pass" in response.json()["detail"]
