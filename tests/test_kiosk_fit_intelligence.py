import cv2
import numpy as np

from src.modules.kiosk_tryon.fit_intelligence import KioskFitIntelligenceService


class FakeFitAnalyzer:
    def __init__(self) -> None:
        self.calls = 0

    def get_runtime_metadata(self):
        return {
            "model": "fake-fit-vl",
            "analyzer_prompt_version": "kiosk-fit-analyzer-v1",
        }

    def analyze_fit_context(self, **kwargs):
        self.calls += 1
        assert kwargs["garment_image"] == b"garment-image"
        return {
            "body_shape_notes": ["broad shoulder impression"],
            "garment_fit_intent": {"silhouette": "regular sports jersey"},
            "visual_fit_risks": ["logo placement should be checked"],
            "measurement_uncertainty": ["front capture only cannot estimate depth"],
            "recommendation_explanation_draft": "Use scorer output for size.",
        }


def _valid_garment_image_bytes() -> bytes:
    image = np.full((640, 640, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (120, 120), (520, 540), (80, 120, 210), -1)
    cv2.putText(
        image,
        "LOGO",
        (210, 340),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.0,
        (255, 255, 255),
        5,
    )
    success, buffer = cv2.imencode(".png", image)
    assert success
    return buffer.tobytes()


def test_kiosk_fit_intelligence_scores_size_with_measurements_and_ai_advice(tmp_path):
    analyzer = FakeFitAnalyzer()
    service = KioskFitIntelligenceService(fit_dir=tmp_path, fit_analyzer=analyzer)

    first = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type="jersey",
        capture_analysis={
            "passed": True,
            "score": 0.94,
            "checks": {"full_body_visible": True},
        },
        front_image=b"front-image",
        side_image=b"side-image",
        garment_image=b"garment-image",
        size_chart=[
            {"size": "M", "chest_cm": 96, "waist_cm": 82},
            {"size": "L", "chest_cm": 102, "waist_cm": 88},
        ],
        body_measurements={"chest_cm": 96, "waist_cm": 82},
        preferred_fit="regular",
    )
    second = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type="jersey",
        capture_analysis={
            "passed": True,
            "score": 0.94,
            "checks": {"full_body_visible": True},
        },
        front_image=b"front-image",
        side_image=b"side-image",
        garment_image=b"garment-image",
        size_chart=[
            {"size": "M", "chest_cm": 96, "waist_cm": 82},
            {"size": "L", "chest_cm": 102, "waist_cm": 88},
        ],
        body_measurements={"chest_cm": 96, "waist_cm": 82},
        preferred_fit="regular",
    )

    assert first.fit_analysis_key.startswith("kiosk-fit:v1:")
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.fit_analysis_key == first.fit_analysis_key
    loaded = service.get_analysis(first.fit_analysis_key)
    assert loaded.cache_hit is True
    assert loaded.fit_analysis_key == first.fit_analysis_key
    assert loaded.size_recommendation["recommended_size"] == "L"
    assert analyzer.calls == 1
    assert first.measurement_estimate["status"] == "provided_measurements"
    assert first.measurement_estimate["scorer_eligible"] is True
    assert first.measurement_estimate["scorer_measurements_cm"] == {
        "chest_cm": 96.0,
        "waist_cm": 82.0,
    }
    assert first.ai_fit_analysis["status"] == "analyzed"
    assert first.ai_fit_analysis["override_policy"] == "advisory_only"
    assert first.size_recommendation["status"] == "recommended"
    assert first.size_recommendation["recommended_size"] == "L"
    assert first.size_recommendation["source"] == "deterministic_scorer"
    assert first.confidence_breakdown["size_match_confidence"] == first.size_recommendation["confidence"]
    assert first.confidence_breakdown["measurement_confidence"] == first.measurement_estimate["confidence"]
    assert first.fit_report["confidence_breakdown"] == first.confidence_breakdown
    assert first.fit_report["agent"]["name"] == "KioskFitAgent"
    assert first.fit_report["agent"]["policy"] == (
        "agent_orchestrates_deterministic_scorer_decides"
    )
    assert first.size_recommendation["candidates"][0]["size"] == "L"
    assert first.fit_assessment["region_fit"]["chest_cm"]["fit_label"] == "aligned"
    assert first.fit_report["recommended_size"] == "L"
    assert first.fit_report["region_assessments"]["waist_cm"]["ease_cm"] == 6.0
    assert first.fit_report["quality_gate"]["status"] == "warning"
    assert (
        first.size_recommendation["shopper_recommendation"]["quality_gate_status"]
        == "warning"
    )
    assert first.fit_report["next_actions"] == [
        "Show recommended size and region fit breakdown to the shopper."
    ]
    assert first.size_scores[0]["size"] == "M"
    assert first.size_scores[0]["score"] is not None
    assert first.size_scores[0]["evaluated_metrics"][0]["metric"] == "chest_cm"
    assert "AI fit analysis is advisory only" in first.warnings[0]


def test_kiosk_fit_intelligence_reports_missing_size_chart(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type=None,
        capture_analysis={"passed": True},
        front_image=b"front-image",
    )

    assert result.size_recommendation["status"] == "missing_size_chart"
    assert result.size_recommendation["recommended_size"] is None
    assert result.ai_fit_analysis["status"] == "not_configured"
    assert result.size_scores == []
    assert "Side capture is missing" in result.warnings[-1]


def test_kiosk_fit_intelligence_does_not_invent_size_without_measurements(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type="jersey",
        capture_analysis={"passed": True},
        front_image=b"front-image",
        size_chart=[{"size": "M", "chest_cm": 96}],
        use_ai_analysis=False,
    )

    assert result.ai_fit_analysis["status"] == "disabled"
    assert result.size_recommendation["status"] == "insufficient_measurements"
    assert result.size_recommendation["recommended_size"] is None
    assert result.size_scores == [
        {
            "size": "M",
            "score": None,
            "risks": [],
            "reason": "No overlapping body measurement and size-chart metric.",
            "evaluated_metrics": [],
            "source": "deterministic_scorer",
        }
    ]
    assert result.fit_report["recommended_size"] is None
    assert result.fit_report["next_actions"] == [
        "Collect body measurements or run a calibrated measurement model.",
        "Use front and side captures with calibration before production sizing.",
    ]


def test_kiosk_fit_intelligence_estimates_size_from_height_and_weight(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type="jersey",
        capture_analysis={"passed": True},
        front_image=b"front-image",
        side_image=b"side-image",
        size_chart=[
            {"size": "M", "chest_cm": 96, "waist_cm": 84},
            {"size": "L", "chest_cm": 102, "waist_cm": 90},
        ],
        body_measurements={"height_cm": 178, "weight_kg": 74},
        preferred_fit="regular",
        use_ai_analysis=False,
    )

    assert result.measurement_estimate["status"] == "height_weight_estimate"
    assert result.measurement_estimate["source"] == "height_weight_estimator"
    assert result.measurement_estimate["scorer_eligible"] is True
    assert result.measurement_estimate["scorer_measurements_cm"] == {
        "chest_cm": 94.5,
        "hip_cm": 93.9,
        "inseam_cm": 80.1,
        "shoulder_cm": 43.9,
        "waist_cm": 81.3,
    }
    assert result.measurement_estimate["confidence"] == 0.45
    assert result.size_recommendation["status"] == "recommended"
    assert result.size_recommendation["recommended_size"] == "L"
    assert "height/weight-derived measurement estimates" in " ".join(result.warnings)


def test_kiosk_fit_intelligence_weights_relaxed_tops_waist_fit(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:relaxed",
        garment_id="garment:v1:tops",
        garment_category="tops",
        garment_type="t-shirt",
        capture_analysis={"passed": True},
        front_image=b"front-image",
        side_image=b"side-image",
        size_chart=[
            {"size": "S", "chest_cm": 88, "waist_cm": 76, "shoulder_cm": 40},
            {"size": "M", "chest_cm": 96, "waist_cm": 84, "shoulder_cm": 43},
            {"size": "L", "chest_cm": 104, "waist_cm": 92, "shoulder_cm": 46},
            {"size": "XL", "chest_cm": 112, "waist_cm": 100, "shoulder_cm": 49},
            {"size": "XXL", "chest_cm": 120, "waist_cm": 108, "shoulder_cm": 52},
        ],
        body_measurements={"height_cm": 170, "weight_kg": 94},
        preferred_fit="relaxed",
        use_ai_analysis=False,
    )

    candidates = {
        candidate["size"]: candidate
        for candidate in result.size_recommendation["candidates"]
    }
    assert result.measurement_estimate["status"] == "height_weight_estimate"
    assert result.measurement_estimate["confidence"] == 0.45
    assert result.size_recommendation["recommended_size"] == "XXL"
    assert candidates["XXL"]["confidence"] > candidates["XL"]["confidence"]
    assert result.fit_report["region_assessments"]["waist_cm"]["fit_label"] == (
        "aligned"
    )
    assert result.confidence_score > 0.7
    assert result.confidence_breakdown["measurement_confidence_label"] == "low"
    assert "measurement_confidence_below_target" in (
        result.confidence_breakdown["target_confidence_blocking_factors"]
    )


def test_kiosk_fit_intelligence_reports_passed_quality_gate_for_ready_inputs(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type="jersey",
        capture_analysis={
            "passed": True,
            "score": 0.94,
            "quality_gates": {
                "category_visual_preview": {
                    "status": "passed",
                    "category_quality_score": 0.96,
                    "target_confidence_ready": True,
                    "recommended_framing": "upper_body",
                    "issues": [],
                    "guidance": [],
                    "metrics": {"estimated_torso_width_px": 240},
                }
            },
        },
        front_image=b"front-image",
        side_image=b"side-image",
        garment_image=_valid_garment_image_bytes(),
        size_chart=[
            {"size": "M", "chest_cm": 96, "waist_cm": 84},
            {"size": "L", "chest_cm": 102, "waist_cm": 90},
        ],
        body_measurements={"height_cm": 178, "weight_kg": 74},
        preferred_fit="regular",
        use_ai_analysis=False,
    )

    gate = result.fit_report["quality_gate"]
    shopper = result.size_recommendation["shopper_recommendation"]
    assert gate["status"] == "passed"
    assert gate["capture_quality"]["status"] == "passed"
    assert gate["capture_quality"]["category_quality_score"] == 0.96
    assert gate["garment_image_quality"]["status"] == "passed"
    assert gate["measurement_quality"]["confidence_label"] == "low"
    assert result.confidence_breakdown["target_confidence"] == 0.85
    assert "measurement_confidence_below_target" in (
        result.confidence_breakdown["target_confidence_blocking_factors"]
    )
    assert shopper["primary_size"] == "L"
    assert shopper["quality_gate_status"] == "passed"


def test_kiosk_fit_intelligence_records_landmark_signals_without_scoring(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:def",
        garment_category="tops",
        garment_type="jersey",
        capture_analysis={
            "passed": True,
            "score": 0.94,
            "checks": {"full_body_visible": True},
            "metrics": {
                "body_height_ratio": 0.8,
                "shoulder_width_ratio": 0.24,
                "hip_width_ratio": 0.16,
                "shoulder_to_hip_ratio": 1.5,
                "front_facing_score": 0.98,
            },
        },
        front_image=b"front-image",
        side_image=b"side-image",
        size_chart=[{"size": "M", "chest_cm": 96}],
        use_ai_analysis=False,
    )

    assert result.measurement_estimate["status"] == "landmark_based_preview"
    assert result.measurement_estimate["source"] == "capture_landmark_ratios"
    assert result.measurement_estimate["scorer_eligible"] is False
    assert result.measurement_estimate["scorer_measurements_cm"] == {}
    assert result.measurement_estimate["estimated_measurements_cm"] == {}
    assert result.measurement_estimate["measurement_signals"] == {
        "body_height_ratio": 0.8,
        "front_facing_score": 0.98,
        "hip_width_ratio": 0.16,
        "shoulder_to_hip_ratio": 1.5,
        "shoulder_width_ratio": 0.24,
    }
    assert result.measurement_estimate["training_sample"]["feature_scope"] == (
        "non_identifying_landmark_ratios"
    )
    assert result.size_recommendation["status"] == "insufficient_measurements"
    assert result.size_recommendation["recommended_size"] is None
    assert result.fit_report["measurement_status"] == "landmark_based_preview"
    landmark_signals = result.fit_report["landmark_fit_signals"]
    assert landmark_signals["status"] == "available"
    assert landmark_signals["sizing_policy"] == "not_used_for_size_recommendation"
    assert landmark_signals["risk_flags"] == ["shoulder_fit_attention"]
    assert "Shoulders appear wider than hips" in landmark_signals["body_shape_hints"][0]
    assert (
        result.fit_assessment["landmark_fit_signals"]["signals"][
            "shoulder_to_hip_ratio"
        ]
        == 1.5
    )
    assert result.size_recommendation["shopper_recommendation"][
        "landmark_fit_hints"
    ] == landmark_signals["body_shape_hints"]


def test_kiosk_fit_intelligence_scores_bottoms_with_inseam(tmp_path):
    service = KioskFitIntelligenceService(fit_dir=tmp_path)

    result = service.analyze_fit(
        session_id="kiosk-session:v1:abc",
        garment_id="garment:v1:shorts",
        garment_category="bottoms",
        garment_type="shorts",
        capture_analysis={"passed": True},
        front_image=b"front-image",
        size_chart=[
            {"size": "M", "waist_cm": 82, "hip_cm": 98, "inseam_cm": 20},
            {"size": "L", "waist_cm": 88, "hip_cm": 104, "inseam_cm": 20},
        ],
        body_measurements={"waist_cm": 82, "hip_cm": 98, "inseam_cm": 20},
        preferred_fit="regular",
        use_ai_analysis=False,
    )

    assert result.size_recommendation["recommended_size"] == "L"
    assert (
        result.fit_report["region_assessments"]["inseam_cm"]["fit_label"] == "aligned"
    )
