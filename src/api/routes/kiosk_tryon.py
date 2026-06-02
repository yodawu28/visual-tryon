"""
Kiosk try-on session API endpoints.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.config.settings import get_settings
from src.modules.kiosk_tryon.capture_analyzer import MediaPipeKioskCaptureAnalyzer
from src.modules.kiosk_tryon.service import KioskTryOnService
from src.schemas.requests import KioskSessionCreateRequest, KioskUserCaptureRequest
from src.schemas.responses import KioskSessionResponse

router = APIRouter(prefix="/api/v1/kiosk", tags=["kiosk-tryon"])


@lru_cache
def get_kiosk_tryon_service() -> KioskTryOnService:
    settings = get_settings()
    return KioskTryOnService(
        session_dir=settings.temp_storage_dir / "kiosk_sessions",
        capture_analyzer=MediaPipeKioskCaptureAnalyzer(),
    )


@router.post("/sessions", response_model=KioskSessionResponse)
async def create_kiosk_session(
    request: KioskSessionCreateRequest,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
) -> KioskSessionResponse:
    result = service.create_session(
        garment_id=request.garment_id,
        avatar_cache_key=request.avatar_cache_key,
        avatar_preview_cache_key=request.avatar_preview_cache_key,
    )
    return _session_response(result, message="Kiosk session created")


@router.get("/sessions/{session_id}", response_model=KioskSessionResponse)
async def get_kiosk_session(
    session_id: str,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
) -> KioskSessionResponse:
    try:
        result = service.get_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _session_response(result, message="Kiosk session loaded")


@router.post(
    "/sessions/{session_id}/captures",
    response_model=KioskSessionResponse,
)
async def add_kiosk_user_capture(
    session_id: str,
    request: KioskUserCaptureRequest,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
) -> KioskSessionResponse:
    try:
        result = service.add_user_capture(
            session_id=session_id,
            front_image=request.front_image,
            side_image=request.side_image,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _session_response(result, message="Kiosk user capture stored")


@router.post(
    "/sessions/{session_id}/captures/analyze",
    response_model=KioskSessionResponse,
)
async def analyze_kiosk_user_capture(
    session_id: str,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
) -> KioskSessionResponse:
    try:
        result = service.analyze_user_capture(session_id=session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _session_response(result, message="Kiosk user capture analyzed")


def _session_response(result: Any, *, message: str) -> KioskSessionResponse:
    payload = _result_to_dict(result)
    return KioskSessionResponse(
        success=True,
        session_id=str(payload["session_id"]),
        status=str(payload["status"]),
        garment_id=payload.get("garment_id"),
        avatar_cache_key=payload.get("avatar_cache_key"),
        avatar_preview_cache_key=payload.get("avatar_preview_cache_key"),
        capture_keys=list(payload.get("capture_keys", [])),
        captures=dict(payload.get("captures", {})),
        capture_analysis=payload.get("capture_analysis"),
        personalized_tryon_key=payload.get("personalized_tryon_key"),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        message=message,
    )


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if is_dataclass(result) and not isinstance(result, type):
        return dict(vars(result))
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    raise TypeError(f"Unsupported kiosk session result type: {type(result)}")
