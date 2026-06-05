"""
Kiosk job handlers.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any

from src.modules.jobs.queue import JobRecord
from src.modules.kiosk_tryon.garment_registry import GarmentRegistry
from src.modules.kiosk_tryon.service import KioskTryOnService
from src.modules.kiosk_tryon.visual_tryon import KioskVisualTryOnService


KIOSK_VISUAL_PREVIEW_JOB_TYPE = "kiosk_visual_preview"
KIOSK_VISUAL_PREVIEW_QUEUE = "gpu.visual_preview"


class KioskVisualPreviewJobHandler:
    def __init__(
        self,
        *,
        session_service: KioskTryOnService,
        garment_registry: GarmentRegistry,
        visual_tryon_service: KioskVisualTryOnService,
    ) -> None:
        self.session_service = session_service
        self.garment_registry = garment_registry
        self.visual_tryon_service = visual_tryon_service

    def handle(self, job: JobRecord) -> dict[str, Any]:
        payload = job.payload
        session_id = _required_str(payload, "session_id")
        garment_id = _required_str(payload, "garment_id")

        session = self.session_service.get_session(session_id)
        session_payload = _result_to_dict(session)
        _require_capture_analysis_passed(session_payload)

        garment = self.garment_registry.get_garment(garment_id)
        if garment is None:
            raise FileNotFoundError(f"Garment not found: {garment_id}")

        result = self.visual_tryon_service.generate_tryon(
            session_id=session_id,
            garment_id=garment.garment_id,
            user_image=self.session_service.read_capture_image(
                session_id=session_id,
                capture_key="front",
            ),
            garment_image=self.garment_registry.read_image(garment.garment_id),
            garment_category=garment.category,
            garment_type=garment.garment_type,
            use_multimodal_analysis=bool(
                payload.get("use_multimodal_analysis", True)
            ),
            size=str(payload.get("size", "1024x1024")),
        )
        result_payload = _result_to_dict(result)

        updated_session = self.session_service.mark_personalized_tryon_ready(
            session_id=session_id,
            personalized_tryon_key=str(result_payload["personalized_tryon_key"]),
        )
        updated_session_payload = _result_to_dict(updated_session)

        return {
            "session_id": session_id,
            "session_status": updated_session_payload["status"],
            "personalized_tryon_key": result_payload["personalized_tryon_key"],
            "personalized_tryon_path": result_payload["personalized_tryon_path"],
            "metadata_path": result_payload["metadata_path"],
            "cache_hit": bool(result_payload.get("cache_hit", False)),
            "model": result_payload["model"],
            "prompt_version": result_payload["prompt_version"],
            "input_mapping": result_payload.get("input_mapping"),
            "generation_time_seconds": result_payload.get("generation_time_seconds"),
            "multimodal_analysis_applied": bool(
                result_payload.get("multimodal_analysis_applied", False)
            ),
            "warnings": list(result_payload.get("warnings", [])),
        }


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _require_capture_analysis_passed(session_payload: dict[str, Any]) -> None:
    analysis = session_payload.get("capture_analysis")
    if not isinstance(analysis, dict) or analysis.get("passed") is not True:
        raise ValueError("capture analysis must pass before visual preview")


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if is_dataclass(result) and not isinstance(result, type):
        return dict(vars(result))
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    raise TypeError(f"Unsupported kiosk job result type: {type(result)}")
