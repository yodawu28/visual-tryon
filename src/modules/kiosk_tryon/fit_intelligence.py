"""
Fit intelligence primitives for kiosk deployments.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.modules.avatar_preview.tryon_analyzer import (
    _prepare_ollama_image_base64,
    _response_content,
)

KIOSK_FIT_ENGINE_VERSION = "kiosk-fit-intelligence-agent-v1"
FIT_ANALYZER_PROMPT_VERSION = "kiosk-fit-analyzer-v1"
MEASUREMENT_ESTIMATOR_VERSION = "landmark-measurement-preview-v1"
BODY_SIZE_MEASUREMENT_KEYS = {
    "chest_cm",
    "waist_cm",
    "hip_cm",
    "shoulder_cm",
    "inseam_cm",
}


@dataclass(frozen=True)
class KioskFitAnalysisResult:
    fit_analysis_key: str
    fit_analysis_path: Path
    cache_hit: bool
    engine_version: str
    measurement_estimate: dict[str, Any]
    ai_fit_analysis: dict[str, Any]
    fit_assessment: dict[str, Any]
    size_scores: list[dict[str, Any]]
    size_recommendation: dict[str, Any]
    fit_report: dict[str, Any]
    confidence_score: float
    confidence_breakdown: dict[str, Any]
    warnings: list[str]


@dataclass(frozen=True)
class KioskFitAgentResult:
    measurement_estimate: dict[str, Any]
    ai_fit_analysis: dict[str, Any]
    fit_assessment: dict[str, Any]
    size_scores: list[dict[str, Any]]
    size_recommendation: dict[str, Any]
    fit_report: dict[str, Any]
    confidence_score: float
    confidence_breakdown: dict[str, Any]
    warnings: list[str]


class OllamaFitAnalyzer:
    """
    Optional multimodal assistant for fit context.

    The analyzer can describe body/garment risks, but it never chooses the final
    recommended size. The deterministic scorer owns that decision.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 300.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "provider": "ollama",
            "model": self.model,
            "analyzer_prompt_version": FIT_ANALYZER_PROMPT_VERSION,
        }

    def analyze_fit_context(
        self,
        *,
        front_image: bytes,
        side_image: bytes | None,
        garment_image: bytes,
        garment_category: str,
        garment_type: str | None,
        preferred_fit: str,
        size_chart: list[dict[str, Any]],
        body_measurements: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = build_fit_analyzer_prompt(
            garment_category=garment_category,
            garment_type=garment_type,
            preferred_fit=preferred_fit,
            size_chart=size_chart,
            body_measurements=body_measurements,
        )
        images = [
            _prepare_ollama_image_base64(front_image),
            _prepare_ollama_image_base64(garment_image),
        ]
        if side_image:
            images.append(_prepare_ollama_image_base64(side_image))

        response = self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt, "images": images}],
                "stream": False,
                "format": "json",
            },
        )
        if response.status_code == 404:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": images,
                    "stream": False,
                    "format": "json",
                },
            )
        response.raise_for_status()
        return parse_fit_analysis_response(_response_content(response.json()))


class LandmarkMeasurementEstimator:
    """
    Low-confidence measurement-estimation scaffold.

    This estimator only records non-identifying landmark ratios from capture
    analysis. It does not produce production body measurements and is not
    eligible for deterministic size scoring until calibration is added.
    """

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "estimator": "landmark_ratio_preview",
            "estimator_version": MEASUREMENT_ESTIMATOR_VERSION,
        }

    def estimate(
        self,
        *,
        capture_analysis: dict[str, Any],
        has_side_capture: bool,
        body_measurements: dict[str, Any],
    ) -> dict[str, Any]:
        return _build_measurement_estimate(
            capture_analysis=capture_analysis,
            has_side_capture=has_side_capture,
            body_measurements=body_measurements,
            estimator_metadata=self.get_runtime_metadata(),
        )


class KioskFitAgent:
    """
    Agent-style fit orchestrator.

    The agent coordinates measurement context, optional AI context, quality gates,
    deterministic size scoring, and shopper-facing recommendation copy. The final
    size decision remains owned by the deterministic scorer.
    """

    def __init__(
        self,
        *,
        fit_analyzer: Any | None = None,
        measurement_estimator: Any | None = None,
    ) -> None:
        self.fit_analyzer = fit_analyzer
        self.measurement_estimator = (
            measurement_estimator or LandmarkMeasurementEstimator()
        )

    def run(
        self,
        *,
        garment_category: str,
        garment_type: str | None,
        capture_analysis: dict[str, Any],
        front_image: bytes,
        side_image: bytes | None,
        garment_image: bytes | None,
        normalized_size_chart: list[dict[str, Any]],
        preferred_fit: str,
        body_measurements: dict[str, Any],
        use_ai_analysis: bool,
    ) -> KioskFitAgentResult:
        warnings: list[str] = []
        measurement_estimate = self.measurement_estimator.estimate(
            capture_analysis=capture_analysis,
            has_side_capture=side_image is not None,
            body_measurements=body_measurements,
        )
        scoring_measurements = dict(
            measurement_estimate.get("scorer_measurements_cm") or {}
        )
        ai_fit_analysis = self._build_ai_fit_analysis(
            front_image=front_image,
            side_image=side_image,
            garment_image=garment_image,
            garment_category=garment_category,
            garment_type=garment_type,
            preferred_fit=preferred_fit,
            normalized_size_chart=normalized_size_chart,
            body_measurements=body_measurements,
            use_ai_analysis=use_ai_analysis,
            warnings=warnings,
        )
        size_scores = _score_size_chart(
            garment_category=garment_category,
            normalized_size_chart=normalized_size_chart,
            body_measurements=scoring_measurements,
            preferred_fit=preferred_fit,
        )
        size_recommendation = _build_size_recommendation(
            normalized_size_chart=normalized_size_chart,
            preferred_fit=preferred_fit,
            body_measurements=scoring_measurements,
            size_scores=size_scores,
        )
        fit_quality_gate = _build_fit_quality_gate(
            garment_category=garment_category,
            capture_analysis=capture_analysis,
            garment_image=garment_image,
            normalized_size_chart=normalized_size_chart,
            measurement_estimate=measurement_estimate,
            size_recommendation=size_recommendation,
        )
        landmark_fit_signals = _build_landmark_fit_signals(
            garment_category=garment_category,
            measurement_estimate=measurement_estimate,
        )
        size_recommendation = {
            **size_recommendation,
            "shopper_recommendation": _build_shopper_recommendation(
                size_recommendation=size_recommendation,
                measurement_estimate=measurement_estimate,
                quality_gate=fit_quality_gate,
                landmark_fit_signals=landmark_fit_signals,
            ),
        }
        fit_assessment = _build_fit_assessment(
            garment_category=garment_category,
            garment_type=garment_type,
            preferred_fit=preferred_fit,
            ai_fit_analysis=ai_fit_analysis,
            size_recommendation=size_recommendation,
            size_scores=size_scores,
            landmark_fit_signals=landmark_fit_signals,
        )
        fit_report = _build_fit_report(
            garment_category=garment_category,
            garment_type=garment_type,
            preferred_fit=preferred_fit,
            measurement_estimate=measurement_estimate,
            ai_fit_analysis=ai_fit_analysis,
            fit_assessment=fit_assessment,
            size_recommendation=size_recommendation,
            size_scores=size_scores,
            quality_gate=fit_quality_gate,
            landmark_fit_signals=landmark_fit_signals,
        )
        confidence_score = _overall_confidence_score(
            size_recommendation=size_recommendation,
            measurement_estimate=measurement_estimate,
            ai_fit_analysis=ai_fit_analysis,
        )
        confidence_breakdown = _build_confidence_breakdown(
            confidence_score=confidence_score,
            size_recommendation=size_recommendation,
            measurement_estimate=measurement_estimate,
            ai_fit_analysis=ai_fit_analysis,
            quality_gate=fit_quality_gate,
        )
        fit_report = {
            **fit_report,
            "agent": self._agent_metadata(),
            "confidence_breakdown": confidence_breakdown,
        }
        warnings.append(
            "AI fit analysis is advisory only; deterministic scorer owns size recommendation."
        )
        if not body_measurements:
            warnings.append(
                "No body measurements were provided; size recommendation remains limited."
            )
        if "height_weight_estimator" in str(measurement_estimate.get("source") or ""):
            warnings.append(
                "Size recommendation uses height/weight-derived measurement estimates; collect detailed measurements or calibrated captures for higher confidence."
            )
        if side_image is None:
            warnings.append(
                "Side capture is missing; future measurement quality will be limited."
            )

        return KioskFitAgentResult(
            measurement_estimate=measurement_estimate,
            ai_fit_analysis=ai_fit_analysis,
            fit_assessment=fit_assessment,
            size_scores=size_scores,
            size_recommendation=size_recommendation,
            fit_report=fit_report,
            confidence_score=confidence_score,
            confidence_breakdown=confidence_breakdown,
            warnings=warnings,
        )

    def _build_ai_fit_analysis(
        self,
        *,
        front_image: bytes,
        side_image: bytes | None,
        garment_image: bytes | None,
        garment_category: str,
        garment_type: str | None,
        preferred_fit: str,
        normalized_size_chart: list[dict[str, Any]],
        body_measurements: dict[str, Any],
        use_ai_analysis: bool,
        warnings: list[str],
    ) -> dict[str, Any]:
        if not use_ai_analysis:
            return _fallback_ai_fit_analysis(status="disabled")
        if self.fit_analyzer is None:
            return _fallback_ai_fit_analysis(status="not_configured")
        if not garment_image:
            warnings.append("AI fit analysis skipped because garment image is missing.")
            return _fallback_ai_fit_analysis(status="missing_garment_image")

        analyzer_metadata = _runtime_metadata(self.fit_analyzer)
        try:
            analysis = self.fit_analyzer.analyze_fit_context(
                front_image=front_image,
                side_image=side_image,
                garment_image=garment_image,
                garment_category=garment_category,
                garment_type=garment_type,
                preferred_fit=preferred_fit,
                size_chart=normalized_size_chart,
                body_measurements=body_measurements,
            )
        except Exception as exc:
            warnings.append(
                f"AI fit analysis failed; deterministic fallback used: {exc}"
            )
            analysis = _fallback_ai_fit_analysis(status="failed")

        return _normalize_ai_fit_analysis(
            analysis=analysis,
            analyzer_metadata=analyzer_metadata,
        )

    def _agent_metadata(self) -> dict[str, Any]:
        return {
            "name": "KioskFitAgent",
            "version": KIOSK_FIT_ENGINE_VERSION,
            "policy": "agent_orchestrates_deterministic_scorer_decides",
            "tools": [
                "landmark_measurement_estimator",
                "optional_multimodal_fit_context",
                "deterministic_size_chart_scorer",
                "fit_quality_gate",
                "shopper_recommendation_composer",
            ],
        }


class KioskFitIntelligenceService:
    """
    Hybrid fit engine.

    AI can enrich body/garment risk notes, but the deterministic scorer owns
    the final size recommendation to avoid hallucinated sizing.
    """

    FIT_PREFIX = "kiosk-fit:v1:"

    def __init__(
        self,
        *,
        fit_dir: Path,
        fit_analyzer: Any | None = None,
        measurement_estimator: Any | None = None,
    ) -> None:
        self.fit_dir = Path(fit_dir)
        self.metadata_dir = self.fit_dir / "metadata"
        self.fit_analyzer = fit_analyzer
        self.measurement_estimator = (
            measurement_estimator or LandmarkMeasurementEstimator()
        )
        self.fit_agent = KioskFitAgent(
            fit_analyzer=self.fit_analyzer,
            measurement_estimator=self.measurement_estimator,
        )
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def analyze_fit(
        self,
        *,
        session_id: str,
        garment_id: str,
        garment_category: str,
        garment_type: str | None,
        capture_analysis: dict[str, Any],
        front_image: bytes,
        side_image: bytes | None = None,
        garment_image: bytes | None = None,
        size_chart: list[dict[str, Any]] | None = None,
        preferred_fit: str = "regular",
        body_measurements: dict[str, Any] | None = None,
        use_ai_analysis: bool = True,
    ) -> KioskFitAnalysisResult:
        if not front_image:
            raise ValueError("front_image must not be empty")
        if capture_analysis.get("passed") is not True:
            raise ValueError("capture analysis must pass before fit analysis")

        normalized_size_chart = _normalize_size_chart(size_chart or [])
        normalized_body_measurements = _normalize_body_measurements(
            body_measurements or {}
        )
        preferred_fit = preferred_fit.strip().lower() or "regular"
        front_sha256 = hashlib.sha256(front_image).hexdigest()
        side_sha256 = hashlib.sha256(side_image).hexdigest() if side_image else None
        garment_sha256 = (
            hashlib.sha256(garment_image).hexdigest() if garment_image else None
        )
        fit_analysis_key = self._build_cache_key(
            session_id=session_id,
            garment_id=garment_id,
            garment_category=garment_category,
            garment_type=garment_type,
            capture_analysis=capture_analysis,
            front_sha256=front_sha256,
            side_sha256=side_sha256,
            garment_sha256=garment_sha256,
            preferred_fit=preferred_fit,
            size_chart=normalized_size_chart,
            body_measurements=normalized_body_measurements,
            use_ai_analysis=use_ai_analysis,
        )
        metadata_path = self._metadata_path(fit_analysis_key)
        cache_hit = metadata_path.exists()

        if cache_hit:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            return self._result_from_payload(
                metadata_path=metadata_path,
                payload=payload,
                cache_hit=True,
            )

        agent_result = self.fit_agent.run(
            garment_category=garment_category,
            garment_type=garment_type,
            capture_analysis=capture_analysis,
            front_image=front_image,
            side_image=side_image,
            garment_image=garment_image,
            normalized_size_chart=normalized_size_chart,
            preferred_fit=preferred_fit,
            body_measurements=normalized_body_measurements,
            use_ai_analysis=use_ai_analysis,
        )

        payload = {
            "fit_analysis_key": fit_analysis_key,
            "session_id": session_id,
            "garment_id": garment_id,
            "garment_category": garment_category,
            "garment_type": garment_type,
            "preferred_fit": preferred_fit,
            "front_image_sha256": front_sha256,
            "side_image_sha256": side_sha256,
            "garment_image_sha256": garment_sha256,
            "engine_version": KIOSK_FIT_ENGINE_VERSION,
            "measurement_estimate": agent_result.measurement_estimate,
            "ai_fit_analysis": agent_result.ai_fit_analysis,
            "fit_assessment": agent_result.fit_assessment,
            "size_scores": agent_result.size_scores,
            "size_recommendation": agent_result.size_recommendation,
            "fit_report": agent_result.fit_report,
            "confidence_score": agent_result.confidence_score,
            "confidence_breakdown": agent_result.confidence_breakdown,
            "warnings": agent_result.warnings,
            "created_at": datetime.now(UTC).isoformat(),
        }
        metadata_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return KioskFitAnalysisResult(
            fit_analysis_key=fit_analysis_key,
            fit_analysis_path=metadata_path,
            cache_hit=False,
            engine_version=KIOSK_FIT_ENGINE_VERSION,
            measurement_estimate=agent_result.measurement_estimate,
            ai_fit_analysis=agent_result.ai_fit_analysis,
            fit_assessment=agent_result.fit_assessment,
            size_scores=agent_result.size_scores,
            size_recommendation=agent_result.size_recommendation,
            fit_report=agent_result.fit_report,
            confidence_score=float(payload["confidence_score"]),
            confidence_breakdown=agent_result.confidence_breakdown,
            warnings=agent_result.warnings,
        )

    def get_analysis(self, fit_analysis_key: str) -> KioskFitAnalysisResult:
        fit_analysis_key = fit_analysis_key.strip()
        if not fit_analysis_key:
            raise ValueError("fit_analysis_key must not be empty")
        if not fit_analysis_key.startswith(self.FIT_PREFIX):
            raise ValueError(f"fit_analysis_key must start with {self.FIT_PREFIX!r}")

        metadata_path = self._metadata_path(fit_analysis_key)
        if not metadata_path.exists():
            raise FileNotFoundError(f"Fit analysis not found: {fit_analysis_key}")

        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        return self._result_from_payload(
            metadata_path=metadata_path,
            payload=payload,
            cache_hit=True,
        )

    def _build_cache_key(
        self,
        *,
        session_id: str,
        garment_id: str,
        garment_category: str,
        garment_type: str | None,
        capture_analysis: dict[str, Any],
        front_sha256: str,
        side_sha256: str | None,
        garment_sha256: str | None,
        preferred_fit: str,
        size_chart: list[dict[str, Any]],
        body_measurements: dict[str, Any],
        use_ai_analysis: bool,
    ) -> str:
        payload = {
            "session_id": session_id,
            "garment_id": garment_id,
            "garment_category": garment_category,
            "garment_type": garment_type,
            "capture_analysis_signature": _capture_analysis_signature(
                capture_analysis
            ),
            "front_sha256": front_sha256,
            "side_sha256": side_sha256,
            "garment_sha256": garment_sha256,
            "preferred_fit": preferred_fit,
            "size_chart": size_chart,
            "body_measurements": body_measurements,
            "use_ai_analysis": use_ai_analysis,
            "scope": "kiosk_fit_intelligence",
            "version": KIOSK_FIT_ENGINE_VERSION,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"{self.FIT_PREFIX}{digest}"

    def _metadata_path(self, fit_analysis_key: str) -> Path:
        return self.metadata_dir / f"{_safe_cache_key_filename(fit_analysis_key)}.json"

    def _result_from_payload(
        self,
        *,
        metadata_path: Path,
        payload: dict[str, Any],
        cache_hit: bool,
    ) -> KioskFitAnalysisResult:
        return KioskFitAnalysisResult(
            fit_analysis_key=str(payload["fit_analysis_key"]),
            fit_analysis_path=metadata_path,
            cache_hit=cache_hit,
            engine_version=str(payload["engine_version"]),
            measurement_estimate=dict(payload["measurement_estimate"]),
            ai_fit_analysis=dict(payload["ai_fit_analysis"]),
            fit_assessment=dict(payload["fit_assessment"]),
            size_scores=list(payload["size_scores"]),
            size_recommendation=dict(payload["size_recommendation"]),
            fit_report=dict(payload.get("fit_report", {})),
            confidence_score=float(payload["confidence_score"]),
            confidence_breakdown=dict(payload.get("confidence_breakdown", {})),
            warnings=list(payload.get("warnings", [])),
        )


def _build_measurement_estimate(
    *,
    capture_analysis: dict[str, Any],
    has_side_capture: bool,
    body_measurements: dict[str, Any],
    estimator_metadata: dict[str, Any],
) -> dict[str, Any]:
    landmark_quality = {
        "capture_analysis_score": capture_analysis.get("score"),
        "front_capture_passed": capture_analysis.get("passed") is True,
        "side_capture_available": has_side_capture,
        "capture_source": capture_analysis.get("capture_source"),
        "capture_source_quality": capture_analysis.get("capture_source_quality", {}),
        "checks": capture_analysis.get("checks", {}),
    }
    measurement_signals = _measurement_signals_from_capture_analysis(capture_analysis)

    if body_measurements:
        direct_measurements = {
            key: value
            for key, value in body_measurements.items()
            if key in BODY_SIZE_MEASUREMENT_KEYS
        }
        if direct_measurements:
            estimated_from_profile = _estimate_measurements_from_height_weight(
                body_measurements
            )
            if estimated_from_profile:
                status = "provided_measurements_with_height_weight_estimate"
                source = "request_body_and_height_weight_estimator"
                scorer_measurements = {
                    **estimated_from_profile,
                    **direct_measurements,
                }
                estimated_measurements = {
                    **body_measurements,
                    **scorer_measurements,
                }
                confidence = 0.66 if has_side_capture else 0.56
                estimation_notes = [
                    "User-provided size measurements are used directly.",
                    "Missing size measurements were estimated from height and weight.",
                ]
            else:
                status = "provided_measurements"
                source = "request_body"
                scorer_measurements = direct_measurements
                estimated_measurements = dict(body_measurements)
                confidence = 0.72 if has_side_capture else 0.62
                estimation_notes = []
        else:
            estimated_from_profile = _estimate_measurements_from_height_weight(
                body_measurements
            )
            if not estimated_from_profile:
                return {
                    "status": "profile_only",
                    "source": "request_body",
                    "estimated_measurements_cm": dict(body_measurements),
                    "scorer_measurements_cm": {},
                    "scorer_eligible": False,
                    "measurement_signals": measurement_signals,
                    "landmark_quality": landmark_quality,
                    "estimator_metadata": estimator_metadata,
                    "confidence": 0.18,
                    "reason": (
                        "Body profile was provided, but no size-chart-compatible "
                        "measurements could be derived."
                    ),
                }
            status = "height_weight_estimate"
            source = "height_weight_estimator"
            scorer_measurements = estimated_from_profile
            estimated_measurements = {
                **body_measurements,
                **estimated_from_profile,
            }
            confidence = 0.45 if has_side_capture else 0.38
            estimation_notes = [
                "Measurements were estimated from height and weight for convenience.",
                "They are not a calibrated body scan and should be treated as low-confidence.",
            ]

        return {
            "status": status,
            "source": source,
            "estimated_measurements_cm": estimated_measurements,
            "scorer_measurements_cm": scorer_measurements,
            "scorer_eligible": True,
            "measurement_signals": measurement_signals,
            "landmark_quality": landmark_quality,
            "estimator_metadata": estimator_metadata,
            "confidence": confidence,
            "estimation_notes": estimation_notes,
        }

    if measurement_signals:
        return {
            "status": "landmark_based_preview",
            "source": "capture_landmark_ratios",
            "estimated_measurements_cm": {},
            "scorer_measurements_cm": {},
            "scorer_eligible": False,
            "measurement_signals": measurement_signals,
            "landmark_quality": landmark_quality,
            "estimator_metadata": estimator_metadata,
            "confidence": 0.28 if has_side_capture else 0.22,
            "reason": (
                "Landmark ratios are useful for future calibration, but they are "
                "not production body measurements."
            ),
            "training_sample": {
                "feature_scope": "non_identifying_landmark_ratios",
                "side_capture_available": has_side_capture,
                "signals": measurement_signals,
            },
            "required_for_production": [
                "camera calibration or reference object",
                "body landmark to measurement model",
                "measurement confidence intervals",
            ],
        }

    return {
        "status": "pending_measurement_model",
        "source": "front_and_optional_side_capture",
        "estimated_measurements_cm": {},
        "scorer_measurements_cm": {},
        "scorer_eligible": False,
        "measurement_signals": {},
        "landmark_quality": landmark_quality,
        "estimator_metadata": estimator_metadata,
        "confidence": 0.0,
        "required_for_production": [
            "camera calibration or reference object",
            "body landmark to measurement model",
            "measurement confidence intervals",
        ],
    }


def _measurement_signals_from_capture_analysis(
    capture_analysis: dict[str, Any],
) -> dict[str, float]:
    metrics = capture_analysis.get("metrics")
    if not isinstance(metrics, dict):
        return {}

    allowed_metrics = {
        "body_height_ratio",
        "shoulder_width_ratio",
        "hip_width_ratio",
        "torso_height_ratio",
        "shoulder_to_hip_ratio",
        "front_facing_score",
    }
    signals: dict[str, float] = {}
    for key in sorted(allowed_metrics):
        value = metrics.get(key)
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        signals[key] = round(numeric_value, 4)
    return signals


def _build_landmark_fit_signals(
    *,
    garment_category: str,
    measurement_estimate: dict[str, Any],
) -> dict[str, Any]:
    signals = measurement_estimate.get("measurement_signals")
    if not isinstance(signals, dict) or not signals:
        return {
            "status": "unavailable",
            "source": measurement_estimate.get("source"),
            "garment_category": garment_category,
            "signals": {},
            "body_shape_hints": [],
            "risk_flags": [],
            "guidance": [
                "Run MediaPipe capture analysis before showing landmark-based fit hints."
            ],
            "sizing_policy": "not_used_for_size_recommendation",
        }

    normalized_category = garment_category.strip().lower()
    body_shape_hints: list[str] = []
    risk_flags: list[str] = []
    guidance: list[str] = []

    shoulder_to_hip = _float_or_none(signals.get("shoulder_to_hip_ratio"))
    shoulder_width = _float_or_none(signals.get("shoulder_width_ratio"))
    hip_width = _float_or_none(signals.get("hip_width_ratio"))
    torso_height = _float_or_none(signals.get("torso_height_ratio"))
    body_height = _float_or_none(signals.get("body_height_ratio"))
    front_facing = _float_or_none(signals.get("front_facing_score"))

    if shoulder_to_hip is not None:
        if shoulder_to_hip >= 1.35:
            body_shape_hints.append("Shoulders appear wider than hips in the capture.")
            if normalized_category not in {"bottoms", "lower_body", "pants", "shorts"}:
                risk_flags.append("shoulder_fit_attention")
                guidance.append(
                    "Review shoulder and chest ease for tops or one-piece garments."
                )
        elif shoulder_to_hip <= 0.95:
            body_shape_hints.append("Hips appear similar to or wider than shoulders.")
            if normalized_category in {
                "bottoms",
                "lower_body",
                "pants",
                "shorts",
                "one_pieces",
                "one-piece",
                "full_body",
                "full_outfit",
                "dress",
                "dresses",
            }:
                risk_flags.append("hip_fit_attention")
                guidance.append(
                    "Review hip and waist ease for bottoms or one-piece garments."
                )
        else:
            body_shape_hints.append("Shoulder and hip proportions look balanced.")

    if torso_height is not None:
        if torso_height < 0.18:
            risk_flags.append("torso_detail_low")
            guidance.append(
                "Use a closer upper-body capture before judging logo or torso details."
            )
        elif torso_height >= 0.28 and normalized_category not in {
            "bottoms",
            "lower_body",
            "pants",
            "shorts",
        }:
            body_shape_hints.append("Torso region has enough landmark coverage for fit hints.")

    if body_height is not None and body_height < 0.65:
        risk_flags.append("body_framing_attention")
        guidance.append(
            "Retake with more full-body framing if lower-body or full-outfit fit is needed."
        )

    if front_facing is not None and front_facing < 0.85:
        risk_flags.append("front_pose_alignment_attention")
        guidance.append(
            "Ask the shopper to face forward for more stable fit and visual preview output."
        )

    if shoulder_width is not None and hip_width is not None:
        body_shape_hints.append(
            f"Pose ratios: shoulder width {shoulder_width:.2f}, hip width {hip_width:.2f}."
        )

    if not guidance:
        guidance.append(
            "Landmark ratios look usable as advisory fit context; keep size scoring deterministic."
        )

    confidence = float(measurement_estimate.get("confidence") or 0.0)
    return {
        "status": "available",
        "source": measurement_estimate.get("source"),
        "garment_category": garment_category,
        "signals": {
            key: value
            for key, value in sorted(signals.items())
            if key
            in {
                "body_height_ratio",
                "shoulder_width_ratio",
                "hip_width_ratio",
                "torso_height_ratio",
                "shoulder_to_hip_ratio",
                "front_facing_score",
            }
        },
        "body_shape_hints": body_shape_hints,
        "risk_flags": sorted(set(risk_flags)),
        "guidance": _dedupe_strings(guidance),
        "confidence": round(confidence, 4),
        "confidence_label": _confidence_label(confidence),
        "sizing_policy": "not_used_for_size_recommendation",
    }


def _estimate_measurements_from_height_weight(
    body_measurements: dict[str, Any],
) -> dict[str, float]:
    height_cm = body_measurements.get("height_cm")
    weight_kg = body_measurements.get("weight_kg")
    if height_cm is None or weight_kg is None:
        return {}

    height = float(height_cm)
    weight = float(weight_kg)
    if height <= 0 or weight <= 0:
        return {}

    height_m = height / 100.0
    bmi_delta = (weight / (height_m * height_m)) - 22.0
    return {
        "chest_cm": round(max(50.0, height * 0.52 + bmi_delta * 1.4), 1),
        "waist_cm": round(max(45.0, height * 0.44 + bmi_delta * 2.2), 1),
        "hip_cm": round(max(50.0, height * 0.52 + bmi_delta * 1.0), 1),
        "shoulder_cm": round(max(30.0, height * 0.245 + bmi_delta * 0.25), 1),
        "inseam_cm": round(max(45.0, height * 0.45), 1),
    }


def _build_fit_assessment(
    *,
    garment_category: str,
    garment_type: str | None,
    preferred_fit: str,
    ai_fit_analysis: dict[str, Any],
    size_recommendation: dict[str, Any],
    size_scores: list[dict[str, Any]],
    landmark_fit_signals: dict[str, Any],
) -> dict[str, Any]:
    best_score = _score_for_size(
        size_scores=size_scores,
        size=size_recommendation.get("recommended_size"),
    )
    region_fit = _region_fit_from_size_score(best_score)
    deterministic_risks = list(best_score.get("risks", [])) if best_score else []
    visual_risks = list(ai_fit_analysis.get("visual_fit_risks", []))
    landmark_risks = list(landmark_fit_signals.get("risk_flags", []))
    return {
        "status": (
            "scored"
            if size_recommendation.get("recommended_size")
            else "needs_measurements"
        ),
        "garment_category": garment_category,
        "garment_type": garment_type,
        "preferred_fit": preferred_fit,
        "region_fit": region_fit,
        "fit_risk_flags": deterministic_risks + visual_risks + landmark_risks,
        "deterministic_fit_risks": deterministic_risks,
        "ai_visual_fit_risks": visual_risks,
        "landmark_fit_signals": landmark_fit_signals,
        "notes": [
            "Visual try-on output is not used as measurement truth.",
            "AI fit analysis cannot override deterministic size scoring.",
            "Pose landmark signals are advisory and cannot choose size without calibration.",
        ],
    }


def _build_size_recommendation(
    *,
    normalized_size_chart: list[dict[str, Any]],
    preferred_fit: str,
    body_measurements: dict[str, Any],
    size_scores: list[dict[str, Any]],
) -> dict[str, Any]:
    if not normalized_size_chart:
        return {
            "status": "missing_size_chart",
            "recommended_size": None,
            "preferred_fit": preferred_fit,
            "candidates": [],
            "reason": "No garment size chart was provided.",
            "source": "deterministic_scorer",
        }

    scored_candidates = [
        score for score in size_scores if score.get("score") is not None
    ]
    if scored_candidates:
        best = max(scored_candidates, key=lambda item: float(item["score"]))
        alternatives = [
            item
            for item in sorted(
                scored_candidates,
                key=lambda item: float(item["score"]),
                reverse=True,
            )
            if item["size"] != best["size"]
        ]
        return {
            "status": "recommended",
            "recommended_size": best["size"],
            "alternative_size": alternatives[0]["size"] if alternatives else None,
            "alternative_sizes": [
                {
                    "size": item["size"],
                    "confidence": round(float(item["score"]), 4),
                    "risks": list(item.get("risks", [])),
                }
                for item in alternatives[:2]
            ],
            "candidates": [
                {
                    "size": item["size"],
                    "confidence": round(float(item["score"]), 4),
                    "risks": list(item.get("risks", [])),
                }
                for item in sorted(
                    scored_candidates,
                    key=lambda item: float(item["score"]),
                    reverse=True,
                )
            ],
            "preferred_fit": preferred_fit,
            "confidence": round(float(best["score"]), 4),
            "source": "deterministic_scorer",
            "reason": "Recommended from provided body measurements and garment size chart.",
            "override_policy": "AI analysis may explain risks but cannot override this size.",
        }

    if not body_measurements:
        reason = "Size chart is available, but body measurements are not estimated yet."
    else:
        reason = "Body measurements do not overlap with available size-chart fields."

    return {
        "status": "insufficient_measurements",
        "recommended_size": None,
        "preferred_fit": preferred_fit,
        "alternative_size": None,
        "alternative_sizes": [],
        "candidates": [],
        "confidence": 0.0,
        "source": "deterministic_scorer",
        "reason": reason,
    }


def _normalize_size_chart(size_chart: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in size_chart:
        raw_size = item.get("size")
        if not isinstance(raw_size, str) or not raw_size.strip():
            raise ValueError("Each size chart item must include a non-empty size")
        normalized.append(
            {
                key: value
                for key, value in {
                    "size": raw_size.strip(),
                    "chest_cm": item.get("chest_cm"),
                    "waist_cm": item.get("waist_cm"),
                    "hip_cm": item.get("hip_cm"),
                    "shoulder_cm": item.get("shoulder_cm"),
                    "length_cm": item.get("length_cm"),
                    "inseam_cm": item.get("inseam_cm"),
                }.items()
                if value is not None
            }
        )
    return normalized


def _normalize_body_measurements(body_measurements: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "height_cm",
        "weight_kg",
        "chest_cm",
        "waist_cm",
        "hip_cm",
        "shoulder_cm",
        "inseam_cm",
    }
    normalized: dict[str, Any] = {}
    for key in sorted(allowed_keys):
        value = body_measurements.get(key)
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric") from exc
        if numeric_value <= 0:
            raise ValueError(f"{key} must be greater than 0")
        normalized[key] = numeric_value
    return normalized


def _score_size_chart(
    *,
    garment_category: str,
    normalized_size_chart: list[dict[str, Any]],
    body_measurements: dict[str, Any],
    preferred_fit: str,
) -> list[dict[str, Any]]:
    metrics = _metrics_for_category(garment_category)
    scores: list[dict[str, Any]] = []
    for item in normalized_size_chart:
        metric_scores: list[float] = []
        risks: list[str] = []
        reasons: list[str] = []
        evaluated_metrics: list[dict[str, Any]] = []
        for metric in metrics:
            body_value = body_measurements.get(metric)
            garment_value = item.get(metric)
            if body_value is None or garment_value is None:
                continue
            metric_weight = _metric_weight_for_scoring(
                garment_category=garment_category,
                metric=metric,
                preferred_fit=preferred_fit,
            )
            metric_target_ease = _metric_target_ease_cm(
                metric=metric,
                preferred_fit=preferred_fit,
            )
            ease = float(garment_value) - float(body_value)
            penalty = abs(ease - metric_target_ease)
            metric_score = max(0.0, 1.0 - (penalty / 24.0))
            if ease < 0:
                metric_score *= 0.35
            fit_label = _metric_fit_label(
                metric=metric,
                ease=ease,
                target_ease=metric_target_ease,
            )
            risk_level = _metric_risk_level(fit_label)
            if fit_label in {"tight", "too_short"}:
                risks.append(f"{metric} may be tight")
            elif fit_label in {"loose", "too_long"}:
                risks.append(f"{metric} may feel loose")
            elif fit_label == "snug":
                risks.append(f"{metric} may feel snug")
            metric_scores.extend([metric_score] * metric_weight)
            reasons.append(
                f"{metric}: garment {garment_value:g}cm vs body {body_value:g}cm"
            )
            evaluated_metrics.append(
                {
                    "metric": metric,
                    "body_cm": round(float(body_value), 2),
                    "garment_cm": round(float(garment_value), 2),
                    "ease_cm": round(ease, 2),
                    "target_ease_cm": round(metric_target_ease, 2),
                    "fit_label": fit_label,
                    "risk_level": risk_level,
                    "score": round(metric_score, 4),
                    "weight": metric_weight,
                    "guidance": _metric_guidance(metric=metric, fit_label=fit_label),
                }
            )

        if metric_scores:
            score = round(sum(metric_scores) / len(metric_scores), 4)
            reason = "; ".join(reasons)
        else:
            score = None
            reason = "No overlapping body measurement and size-chart metric."

        scores.append(
            {
                "size": item["size"],
                "score": score,
                "risks": risks,
                "reason": reason,
                "evaluated_metrics": evaluated_metrics,
                "source": "deterministic_scorer",
            }
        )
    return scores


def _metrics_for_category(garment_category: str) -> list[str]:
    normalized = garment_category.strip().lower()
    if normalized in {"bottoms", "lower_body", "lower-body", "pants", "shorts"}:
        return ["waist_cm", "hip_cm", "inseam_cm"]
    if normalized in {
        "one_pieces",
        "one-piece",
        "full_body",
        "full_outfit",
        "dress",
        "dresses",
    }:
        return ["chest_cm", "waist_cm", "hip_cm", "shoulder_cm"]
    return ["chest_cm", "waist_cm", "shoulder_cm"]


def _metric_weight_for_scoring(
    *,
    garment_category: str,
    metric: str,
    preferred_fit: str,
) -> int:
    normalized_category = garment_category.strip().lower()
    normalized_fit = preferred_fit.strip().lower()
    if normalized_category in {"tops", "upper_body", "upper-body"}:
        if metric == "waist_cm" and normalized_fit in {
            "relaxed",
            "comfort",
            "loose",
            "oversized",
        }:
            return 2
    if normalized_category in {"bottoms", "lower_body", "lower-body", "pants", "shorts"}:
        if metric in {"waist_cm", "hip_cm"}:
            return 2
    return 1


def _target_ease_cm(preferred_fit: str) -> float:
    normalized = preferred_fit.strip().lower()
    if normalized in {"slim", "fitted", "tight"}:
        return 3.0
    if normalized in {"relaxed", "comfort"}:
        return 10.0
    if normalized in {"loose", "oversized"}:
        return 14.0
    return 6.0


def _metric_target_ease_cm(*, metric: str, preferred_fit: str) -> float:
    if metric == "inseam_cm":
        return 0.0
    if metric == "shoulder_cm":
        normalized = preferred_fit.strip().lower()
        if normalized in {"slim", "fitted", "tight"}:
            return 1.0
        if normalized in {"relaxed", "comfort", "loose", "oversized"}:
            return 3.0
        return 2.0
    return _target_ease_cm(preferred_fit)


def _metric_fit_label(*, metric: str, ease: float, target_ease: float) -> str:
    if metric == "inseam_cm":
        if ease < -3:
            return "too_short"
        if ease > 4:
            return "too_long"
        return "aligned"
    if ease < 0:
        return "tight"
    if ease < target_ease - 4:
        return "snug"
    if ease <= target_ease + 4:
        return "aligned"
    if ease <= target_ease + 12:
        return "relaxed"
    return "loose"


def _metric_risk_level(fit_label: str) -> str:
    if fit_label in {"tight", "too_short", "loose", "too_long"}:
        return "high"
    if fit_label in {"snug", "relaxed"}:
        return "medium"
    return "low"


def _metric_guidance(*, metric: str, fit_label: str) -> str:
    metric_label = metric.removesuffix("_cm").replace("_", " ")
    if fit_label in {"tight", "too_short"}:
        return f"{metric_label} may need a larger size or a different cut."
    if fit_label == "snug":
        return f"{metric_label} is close to body measurement for the selected fit."
    if fit_label == "aligned":
        return f"{metric_label} is aligned with the selected fit preference."
    if fit_label == "relaxed":
        return f"{metric_label} has extra ease and may feel comfortable."
    return f"{metric_label} may need a smaller size or a less relaxed cut."


def _score_for_size(
    *,
    size_scores: list[dict[str, Any]],
    size: Any,
) -> dict[str, Any] | None:
    if not size:
        return None
    for score in size_scores:
        if score.get("size") == size:
            return score
    return None


def _region_fit_from_size_score(size_score: dict[str, Any] | None) -> dict[str, Any]:
    if not size_score:
        return {}
    region_fit: dict[str, Any] = {}
    for metric in size_score.get("evaluated_metrics", []):
        if not isinstance(metric, dict):
            continue
        metric_name = str(metric.get("metric") or "")
        if not metric_name:
            continue
        region_fit[metric_name] = {
            "fit_label": metric.get("fit_label"),
            "risk_level": metric.get("risk_level"),
            "ease_cm": metric.get("ease_cm"),
            "target_ease_cm": metric.get("target_ease_cm"),
            "guidance": metric.get("guidance"),
        }
    return region_fit


def _build_fit_report(
    *,
    garment_category: str,
    garment_type: str | None,
    preferred_fit: str,
    measurement_estimate: dict[str, Any],
    ai_fit_analysis: dict[str, Any],
    fit_assessment: dict[str, Any],
    size_recommendation: dict[str, Any],
    size_scores: list[dict[str, Any]],
    quality_gate: dict[str, Any],
    landmark_fit_signals: dict[str, Any],
) -> dict[str, Any]:
    recommended_size = size_recommendation.get("recommended_size")
    best_score = _score_for_size(size_scores=size_scores, size=recommended_size)
    return {
        "status": size_recommendation.get("status"),
        "garment": {
            "category": garment_category,
            "type": garment_type,
            "preferred_fit": preferred_fit,
        },
        "recommended_size": recommended_size,
        "alternative_sizes": list(size_recommendation.get("alternative_sizes", [])),
        "confidence_score": size_recommendation.get("confidence", 0.0),
        "user_summary": _fit_user_summary(
            size_recommendation=size_recommendation,
            best_score=best_score,
        ),
        "region_assessments": _region_fit_from_size_score(best_score),
        "fit_risks": list(fit_assessment.get("fit_risk_flags", [])),
        "measurement_status": measurement_estimate.get("status"),
        "landmark_fit_signals": landmark_fit_signals,
        "quality_gate": quality_gate,
        "ai_notes": {
            "status": ai_fit_analysis.get("status"),
            "body_shape_notes": list(ai_fit_analysis.get("body_shape_notes", [])),
            "visual_fit_risks": list(ai_fit_analysis.get("visual_fit_risks", [])),
            "measurement_uncertainty": list(
                ai_fit_analysis.get("measurement_uncertainty", [])
            ),
            "override_policy": ai_fit_analysis.get("override_policy"),
        },
        "next_actions": _fit_next_actions(
            size_recommendation=size_recommendation,
            measurement_estimate=measurement_estimate,
        ),
    }


def _build_fit_quality_gate(
    *,
    garment_category: str,
    capture_analysis: dict[str, Any],
    garment_image: bytes | None,
    normalized_size_chart: list[dict[str, Any]],
    measurement_estimate: dict[str, Any],
    size_recommendation: dict[str, Any],
) -> dict[str, Any]:
    capture_gate = _capture_category_gate(capture_analysis)
    garment_quality = _garment_image_quality(garment_image)
    measurement_status = str(measurement_estimate.get("status") or "unknown")
    measurement_confidence = float(measurement_estimate.get("confidence") or 0.0)
    size_status = str(size_recommendation.get("status") or "unknown")

    category_capture_status = str(capture_gate.get("status") or "unknown")
    checks = {
        "capture_passed": capture_analysis.get("passed") is True,
        "category_capture_ready": category_capture_status
        in {"passed", "warning", "unknown"},
        "size_chart_available": bool(normalized_size_chart),
        "measurement_basis_available": bool(
            measurement_estimate.get("scorer_measurements_cm")
        ),
        "garment_image_available": garment_image is not None,
        "garment_image_decode_ok": bool(
            garment_quality.get("checks", {}).get("garment_image_decode_ok")
        ),
        "garment_image_large_enough": bool(
            garment_quality.get("checks", {}).get("garment_image_large_enough")
        ),
        "garment_image_sharp_enough": bool(
            garment_quality.get("checks", {}).get("garment_image_sharp_enough")
        ),
    }

    critical_checks = {
        "capture_passed": checks["capture_passed"],
        "category_capture_ready": checks["category_capture_ready"],
        "size_chart_available": checks["size_chart_available"],
        "measurement_basis_available": checks["measurement_basis_available"],
    }
    critical_issues = [
        key for key, passed in critical_checks.items() if passed is not True
    ]
    warning_issues = [key for key, passed in checks.items() if passed is not True]

    if critical_issues:
        status = "failed"
    elif warning_issues:
        status = "warning"
    else:
        status = "passed"

    return {
        "status": status,
        "garment_category": garment_category,
        "size_recommendation_status": size_status,
        "checks": checks,
        "critical_checks": critical_checks,
        "issues": warning_issues,
        "critical_issues": critical_issues,
        "capture_quality": {
            "status": category_capture_status,
            "category_quality_score": round(
                float(capture_gate.get("category_quality_score") or 0.0),
                4,
            ),
            "target_confidence_ready": capture_gate.get("target_confidence_ready")
            is True,
            "capture_protocol_quality": dict(
                capture_analysis.get("capture_protocol_quality") or {}
            ),
            "recommended_framing": capture_gate.get("recommended_framing"),
            "issues": list(capture_gate.get("issues", [])),
            "guidance": list(capture_gate.get("guidance", [])),
            "metrics": dict(capture_gate.get("metrics", {})),
        },
        "garment_image_quality": garment_quality,
        "measurement_quality": {
            "status": measurement_status,
            "confidence": round(measurement_confidence, 4),
            "confidence_label": _confidence_label(measurement_confidence),
            "scorer_eligible": measurement_estimate.get("scorer_eligible") is True,
            "source": measurement_estimate.get("source"),
        },
        "guidance": _fit_quality_gate_guidance(
            critical_issues=critical_issues,
            warning_issues=warning_issues,
            capture_gate=capture_gate,
        ),
    }


def _capture_category_gate(capture_analysis: dict[str, Any]) -> dict[str, Any]:
    quality_gates = capture_analysis.get("quality_gates")
    if not isinstance(quality_gates, dict):
        return {}
    category_gate = quality_gates.get("category_visual_preview")
    if not isinstance(category_gate, dict):
        return {}
    return category_gate


def _garment_image_quality(garment_image: bytes | None) -> dict[str, Any]:
    if garment_image is None:
        return {
            "status": "missing",
            "checks": {
                "garment_image_decode_ok": False,
                "garment_image_large_enough": False,
                "garment_image_sharp_enough": False,
            },
            "metrics": {},
            "guidance": ["Upload a garment image before judging visual fit quality."],
        }

    try:
        import cv2
        import numpy as np
    except ImportError:
        return {
            "status": "unknown",
            "checks": {
                "garment_image_decode_ok": False,
                "garment_image_large_enough": False,
                "garment_image_sharp_enough": False,
            },
            "metrics": {},
            "guidance": ["Install image quality dependencies to score garment inputs."],
        }

    image = cv2.imdecode(np.frombuffer(garment_image, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return {
            "status": "invalid_image",
            "checks": {
                "garment_image_decode_ok": False,
                "garment_image_large_enough": False,
                "garment_image_sharp_enough": False,
            },
            "metrics": {"byte_size": len(garment_image)},
            "guidance": ["Use a valid PNG, JPEG, or WEBP garment image."],
        }

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    checks = {
        "garment_image_decode_ok": True,
        "garment_image_large_enough": min(width, height) >= 512,
        "garment_image_sharp_enough": blur_variance >= 80.0,
    }
    issues = [key for key, passed in checks.items() if not passed]
    return {
        "status": "passed" if not issues else "warning",
        "checks": checks,
        "issues": issues,
        "metrics": {
            "width_px": width,
            "height_px": height,
            "blur_variance": round(blur_variance, 4),
            "brightness": round(brightness, 4),
        },
        "guidance": _garment_quality_guidance(issues),
    }


def _garment_quality_guidance(issues: list[str]) -> list[str]:
    guidance: list[str] = []
    if "garment_image_large_enough" in issues:
        guidance.append("Use a garment image at least 512px on the shorter side.")
    if "garment_image_sharp_enough" in issues:
        guidance.append("Use a sharper garment image so logo and text survive VTON.")
    return guidance


def _fit_quality_gate_guidance(
    *,
    critical_issues: list[str],
    warning_issues: list[str],
    capture_gate: dict[str, Any],
) -> list[str]:
    guidance: list[str] = []
    if "size_chart_available" in critical_issues:
        guidance.append("Attach a size chart before presenting size recommendation.")
    if "measurement_basis_available" in critical_issues:
        guidance.append(
            "Collect height and weight, detailed body measurements, or calibrated scan measurements."
        )
    if "capture_passed" in critical_issues:
        guidance.append("Run capture analysis and retake the photo until it passes.")
    if "category_capture_ready" in critical_issues:
        guidance.extend(list(capture_gate.get("guidance", [])))
    if "garment_image_large_enough" in warning_issues:
        guidance.append("Use a larger garment image for sharper visual preview.")
    if "garment_image_sharp_enough" in warning_issues:
        guidance.append("Use a less blurry garment image for logo/text fidelity.")
    return guidance


def _build_shopper_recommendation(
    *,
    size_recommendation: dict[str, Any],
    measurement_estimate: dict[str, Any],
    quality_gate: dict[str, Any],
    landmark_fit_signals: dict[str, Any],
) -> dict[str, Any]:
    recommended_size = size_recommendation.get("recommended_size")
    confidence = float(size_recommendation.get("confidence") or 0.0)
    quality_status = str(quality_gate.get("status") or "unknown")
    if not recommended_size:
        message = str(
            size_recommendation.get("reason")
            or "More measurements are needed before recommending a size."
        )
    else:
        message = (
            f"Recommended size: {recommended_size}. "
            f"Confidence is {_confidence_label(confidence)}."
        )
        if quality_status != "passed":
            message += (
                " Review quality gate guidance before using this as final advice."
            )

    return {
        "primary_size": recommended_size,
        "alternative_size": size_recommendation.get("alternative_size"),
        "confidence": round(confidence, 4),
        "confidence_label": _confidence_label(confidence),
        "quality_gate_status": quality_status,
        "measurement_status": measurement_estimate.get("status"),
        "landmark_fit_hints": list(
            landmark_fit_signals.get("body_shape_hints", [])
        ),
        "message": message,
    }


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.55:
        return "medium"
    if confidence > 0:
        return "low"
    return "unavailable"


def _fit_user_summary(
    *,
    size_recommendation: dict[str, Any],
    best_score: dict[str, Any] | None,
) -> str:
    recommended_size = size_recommendation.get("recommended_size")
    if not recommended_size:
        return str(size_recommendation.get("reason") or "More fit data is required.")
    risks = list(best_score.get("risks", [])) if best_score else []
    if risks:
        return (
            f"Size {recommended_size} is the best deterministic match, "
            f"with fit risks: {', '.join(risks)}."
        )
    return (
        f"Size {recommended_size} is the best deterministic match for the selected fit."
    )


def _fit_next_actions(
    *,
    size_recommendation: dict[str, Any],
    measurement_estimate: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    if not size_recommendation.get("recommended_size"):
        actions.append(
            "Collect body measurements or run a calibrated measurement model."
        )
    if measurement_estimate.get("status") != "provided_measurements":
        actions.append(
            "Use front and side captures with calibration before production sizing."
        )
    if not actions:
        actions.append("Show recommended size and region fit breakdown to the shopper.")
    return actions


def _fallback_ai_fit_analysis(*, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "source": "deterministic_fallback",
        "body_shape_notes": [],
        "garment_fit_intent": {},
        "visual_fit_risks": [],
        "measurement_uncertainty": [],
        "recommendation_explanation_draft": "",
    }


def _normalize_ai_fit_analysis(
    *,
    analysis: dict[str, Any],
    analyzer_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": str(analysis.get("status") or "analyzed"),
        "source": "ai_fit_analyzer",
        "analyzer_model": analyzer_metadata.get("model"),
        "analyzer_prompt_version": analyzer_metadata.get("analyzer_prompt_version"),
        "body_shape_notes": _string_list(analysis.get("body_shape_notes")),
        "garment_fit_intent": (
            analysis.get("garment_fit_intent")
            if isinstance(analysis.get("garment_fit_intent"), dict)
            else {}
        ),
        "visual_fit_risks": _string_list(analysis.get("visual_fit_risks")),
        "measurement_uncertainty": _string_list(
            analysis.get("measurement_uncertainty")
        ),
        "recommendation_explanation_draft": str(
            analysis.get("recommendation_explanation_draft") or ""
        ),
        "override_policy": "advisory_only",
    }


def parse_fit_analysis_response(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if not isinstance(response, str):
        raise ValueError("Fit analyzer response must be a JSON object or string")
    stripped = response.strip()
    if "```" in stripped:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Fit analyzer response must include a JSON object")
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Fit analyzer response must include a JSON object")
    return parsed


def build_fit_analyzer_prompt(
    *,
    garment_category: str,
    garment_type: str | None,
    preferred_fit: str,
    size_chart: list[dict[str, Any]],
    body_measurements: dict[str, Any],
) -> str:
    return (
        "You are a fit-analysis assistant for a kiosk apparel flow. Return JSON "
        "only. Do not recommend the final size. Do not invent exact body "
        "measurements. The deterministic size scorer will choose size from the "
        "size chart.\n\n"
        "Images: IMAGE 1 is the front user capture, IMAGE 2 is the garment image, "
        "and IMAGE 3 may be an optional side capture.\n"
        f"garment_category={garment_category}; garment_type={garment_type or 'unknown'}; "
        f"preferred_fit={preferred_fit}; "
        f"provided_body_measurements={json.dumps(body_measurements, sort_keys=True)}; "
        f"size_chart={json.dumps(size_chart, sort_keys=True)}.\n\n"
        "Return exactly one JSON object with keys: body_shape_notes (list), "
        "garment_fit_intent (object), visual_fit_risks (list), "
        "measurement_uncertainty (list), recommendation_explanation_draft "
        "(string). Keep the explanation conditional and do not choose a size."
    )


def _overall_confidence_score(
    *,
    size_recommendation: dict[str, Any],
    measurement_estimate: dict[str, Any],
    ai_fit_analysis: dict[str, Any],
) -> float:
    recommendation_confidence = float(size_recommendation.get("confidence") or 0.0)
    if recommendation_confidence <= 0:
        return 0.2 if ai_fit_analysis.get("status") == "analyzed" else 0.15
    measurement_confidence = float(measurement_estimate.get("confidence") or 0.5)
    ai_bonus = 0.05 if ai_fit_analysis.get("status") == "analyzed" else 0.0
    weighted_confidence = (
        recommendation_confidence * 0.7
        + measurement_confidence * 0.25
        + ai_bonus
    )
    return round(
        min(0.95, weighted_confidence),
        4,
    )


def _build_confidence_breakdown(
    *,
    confidence_score: float,
    size_recommendation: dict[str, Any],
    measurement_estimate: dict[str, Any],
    ai_fit_analysis: dict[str, Any],
    quality_gate: dict[str, Any],
) -> dict[str, Any]:
    size_match_confidence = float(size_recommendation.get("confidence") or 0.0)
    measurement_confidence = float(measurement_estimate.get("confidence") or 0.0)
    ai_advisory_bonus = 0.05 if ai_fit_analysis.get("status") == "analyzed" else 0.0
    checks = dict(quality_gate.get("checks") or {})
    capture_quality = dict(quality_gate.get("capture_quality") or {})
    garment_quality = dict(quality_gate.get("garment_image_quality") or {})
    garment_checks = dict(garment_quality.get("checks") or {})
    category_quality_score = float(capture_quality.get("category_quality_score") or 0.0)
    protocol_quality = dict(capture_quality.get("capture_protocol_quality") or {})
    capture_confidence = _capture_confidence_score(
        category_quality_score=category_quality_score,
        protocol_quality=protocol_quality,
        capture_passed=checks.get("capture_passed") is True,
    )
    garment_input_confidence = _garment_input_confidence_score(garment_checks)
    size_chart_confidence = 1.0 if checks.get("size_chart_available") is True else 0.0
    target_confidence = 0.85
    target_blocking_factors = _target_confidence_blocking_factors(
        capture_confidence=capture_confidence,
        measurement_confidence=measurement_confidence,
        size_chart_confidence=size_chart_confidence,
        garment_input_confidence=garment_input_confidence,
        confidence_score=float(confidence_score),
        target_confidence=target_confidence,
    )
    return {
        "overall_confidence": round(float(confidence_score), 4),
        "overall_confidence_label": _confidence_label(float(confidence_score)),
        "size_match_confidence": round(size_match_confidence, 4),
        "size_match_confidence_label": _confidence_label(size_match_confidence),
        "measurement_confidence": round(measurement_confidence, 4),
        "measurement_confidence_label": _confidence_label(measurement_confidence),
        "measurement_status": measurement_estimate.get("status"),
        "measurement_source": measurement_estimate.get("source"),
        "ai_advisory_bonus": round(ai_advisory_bonus, 4),
        "quality_gate_status": quality_gate.get("status"),
        "capture_confidence": round(capture_confidence, 4),
        "capture_confidence_label": _confidence_label(capture_confidence),
        "size_chart_confidence": round(size_chart_confidence, 4),
        "garment_input_confidence": round(garment_input_confidence, 4),
        "target_confidence": target_confidence,
        "target_confidence_met": float(confidence_score) >= target_confidence,
        "target_confidence_eligible": not target_blocking_factors,
        "target_confidence_blocking_factors": target_blocking_factors,
        "display_guidance": (
            "Show size match confidence separately from overall confidence. "
            "Overall confidence is a weighted data-confidence score and remains "
            "below target when measurements are estimated from height/weight or "
            "uncalibrated landmarks."
        ),
        "confidence_formula": {
            "size_match_weight": 0.7,
            "measurement_basis_weight": 0.25,
            "ai_advisory_bonus": round(ai_advisory_bonus, 4),
        },
        "upgrade_path": [
            "Collect detailed body measurements from the shopper.",
            "Use calibrated camera captures before treating landmark ratios as measurements.",
            "Keep garment size charts complete for the selected region/category.",
        ],
    }


def _capture_confidence_score(
    *,
    category_quality_score: float,
    protocol_quality: dict[str, Any],
    capture_passed: bool,
) -> float:
    if not capture_passed:
        return 0.0
    protocol_bonus = (
        0.08 if protocol_quality.get("target_confidence_signal") is True else 0.0
    )
    return round(min(1.0, max(0.0, category_quality_score) + protocol_bonus), 4)


def _garment_input_confidence_score(garment_checks: dict[str, Any]) -> float:
    required = [
        "garment_image_decode_ok",
        "garment_image_large_enough",
        "garment_image_sharp_enough",
    ]
    if not garment_checks:
        return 0.0
    return round(
        sum(1 for key in required if garment_checks.get(key) is True) / len(required),
        4,
    )


def _target_confidence_blocking_factors(
    *,
    capture_confidence: float,
    measurement_confidence: float,
    size_chart_confidence: float,
    garment_input_confidence: float,
    confidence_score: float,
    target_confidence: float,
) -> list[str]:
    factors: list[str] = []
    if capture_confidence < 0.85:
        factors.append("capture_quality_below_target")
    if measurement_confidence < 0.85:
        factors.append("measurement_confidence_below_target")
    if size_chart_confidence < 1.0:
        factors.append("size_chart_missing")
    if garment_input_confidence < 0.85:
        factors.append("garment_input_quality_below_target")
    if confidence_score < target_confidence:
        factors.append("overall_confidence_below_target")
    return factors


def _capture_analysis_signature(capture_analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": capture_analysis.get("passed"),
        "score": capture_analysis.get("score"),
        "capture_source": capture_analysis.get("capture_source"),
        "capture_protocol_quality": capture_analysis.get(
            "capture_protocol_quality",
            {},
        ),
        "checks": capture_analysis.get("checks", {}),
        "metrics": {
            key: value
            for key, value in dict(capture_analysis.get("metrics") or {}).items()
            if key
            in {
                "body_height_ratio",
                "shoulder_width_ratio",
                "hip_width_ratio",
                "torso_height_ratio",
                "shoulder_to_hip_ratio",
                "front_facing_score",
            }
        },
        "quality_gates": capture_analysis.get("quality_gates", {}),
    }


def _runtime_metadata(analyzer: Any) -> dict[str, Any]:
    if hasattr(analyzer, "get_runtime_metadata"):
        metadata = analyzer.get_runtime_metadata()
        if isinstance(metadata, dict):
            return metadata
    return {}


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = str(value).strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        deduped.append(stripped)
    return deduped


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]


def _safe_cache_key_filename(cache_key: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", cache_key)
    if not safe_name.strip(".-"):
        raise ValueError("Invalid kiosk fit analysis cache key")
    return safe_name
