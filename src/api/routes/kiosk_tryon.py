"""
Kiosk try-on session API endpoints.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from src.config.settings import get_settings
from src.modules.avatar_preview.tryon_analyzer import OllamaTryOnAnalyzer
from src.modules.image_generator.replicate_avatar_preview_generator import (
    ReplicateAvatarPreviewGenerator,
)
from src.modules.kiosk_tryon.capture_analyzer import MediaPipeKioskCaptureAnalyzer
from src.modules.kiosk_tryon.fit_intelligence import (
    KioskFitIntelligenceService,
    OllamaFitAnalyzer,
)
from src.modules.kiosk_tryon.garment_registry import GarmentRecord, GarmentRegistry
from src.modules.kiosk_tryon.service import KioskTryOnService
from src.modules.kiosk_tryon.visual_tryon import KioskVisualTryOnService
from src.schemas.requests import KioskFitAnalysisRequest, KioskSessionCreateRequest
from src.schemas.responses import (
    KioskFitAnalysisResponse,
    KioskGarmentListResponse,
    KioskGarmentRecordResponse,
    KioskGarmentResponse,
    KioskPersonalizedTryOnResponse,
    KioskSessionResponse,
)

router = APIRouter(prefix="/api/v1/kiosk", tags=["kiosk-tryon"])


@lru_cache
def get_kiosk_garment_registry() -> GarmentRegistry:
    settings = get_settings()
    garment_dir = settings.temp_storage_dir / "garments"
    return GarmentRegistry(
        db_path=garment_dir / "garments.sqlite3",
        image_dir=garment_dir / "images",
    )


@lru_cache
def get_kiosk_tryon_service() -> KioskTryOnService:
    settings = get_settings()
    return KioskTryOnService(
        session_dir=settings.temp_storage_dir / "kiosk_sessions",
        capture_analyzer=MediaPipeKioskCaptureAnalyzer(),
        garment_registry=get_kiosk_garment_registry(),
    )


@lru_cache
def get_kiosk_visual_tryon_service() -> KioskVisualTryOnService:
    settings = get_settings()
    return KioskVisualTryOnService(
        tryon_dir=settings.temp_storage_dir / "kiosk_tryons",
        generator=ReplicateAvatarPreviewGenerator(),
        tryon_analyzer=OllamaTryOnAnalyzer(
            model=settings.tryon_analyzer_ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.tryon_analyzer_timeout,
        ),
    )


@lru_cache
def get_kiosk_fit_intelligence_service() -> KioskFitIntelligenceService:
    settings = get_settings()
    return KioskFitIntelligenceService(
        fit_dir=settings.temp_storage_dir / "kiosk_fit",
        fit_analyzer=OllamaFitAnalyzer(
            model=settings.tryon_analyzer_ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.tryon_analyzer_timeout,
        ),
    )


@router.post("/garments", response_model=KioskGarmentResponse)
async def upload_kiosk_garment(
    file: UploadFile = File(..., description="Garment image file"),
    category: str = Form(
        ..., description="Garment category: tops, bottoms, one_pieces"
    ),
    name: str | None = Form(default=None, description="Optional garment display name"),
    garment_type: str | None = Form(
        default=None,
        description="Optional garment type such as jersey, t-shirt, shorts",
    ),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
) -> KioskGarmentResponse:
    settings = get_settings()
    image_bytes = await file.read()
    try:
        record = registry.create_garment(
            image_bytes=image_bytes,
            category=category,
            name=name,
            garment_type=garment_type,
            original_filename=file.filename,
            max_size_bytes=settings.max_upload_size_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return KioskGarmentResponse(
        success=True,
        garment=_garment_record_response(record),
        message="Kiosk garment uploaded",
    )


@router.get("/garments", response_model=KioskGarmentListResponse)
async def list_kiosk_garments(
    limit: int = Query(default=100, ge=1, le=500),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
) -> KioskGarmentListResponse:
    records = registry.list_garments(limit=limit)
    return KioskGarmentListResponse(
        success=True,
        garments=[_garment_record_response(record) for record in records],
        count=len(records),
        message="Kiosk garments loaded",
    )


@router.get("/garments/{garment_id}", response_model=KioskGarmentResponse)
async def get_kiosk_garment(
    garment_id: str,
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
) -> KioskGarmentResponse:
    record = registry.get_garment(garment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Garment not found: {garment_id}")
    return KioskGarmentResponse(
        success=True,
        garment=_garment_record_response(record),
        message="Kiosk garment loaded",
    )


@router.post("/sessions", response_model=KioskSessionResponse)
async def create_kiosk_session(
    request: KioskSessionCreateRequest,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
) -> KioskSessionResponse:
    try:
        result = service.create_session(
            garment_id=request.garment_id,
            avatar_cache_key=request.avatar_cache_key,
            avatar_preview_cache_key=request.avatar_preview_cache_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    front_image: UploadFile = File(
        ...,
        description="Front-facing user capture from the kiosk webcam",
    ),
    side_image: UploadFile | None = File(
        default=None,
        description="Optional side-facing user capture from the kiosk webcam",
    ),
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
) -> KioskSessionResponse:
    settings = get_settings()
    try:
        front_image_bytes = await _read_capture_upload(
            front_image,
            field_name="front_image",
            max_size_bytes=settings.max_upload_size_bytes,
        )
        side_image_bytes = (
            await _read_capture_upload(
                side_image,
                field_name="side_image",
                max_size_bytes=settings.max_upload_size_bytes,
            )
            if side_image is not None
            else None
        )
        result = service.add_user_capture(
            session_id=session_id,
            front_image=front_image_bytes,
            side_image=side_image_bytes,
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


@router.post(
    "/sessions/{session_id}/visual-preview",
    response_model=KioskPersonalizedTryOnResponse,
    summary="Generate optional kiosk visual preview",
)
async def generate_kiosk_visual_preview(
    session_id: str,
    use_multimodal_analysis: bool = Query(
        default=True,
        description=(
            "Use the configured multimodal analyzer before Qwen-style visual "
            "preview generation. This is optional and is not used by Fit "
            "Intelligence."
        ),
    ),
    size: str = Query(
        default="1024x1024", description="Requested generated image size"
    ),
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
    visual_tryon_service: KioskVisualTryOnService = Depends(
        get_kiosk_visual_tryon_service
    ),
) -> KioskPersonalizedTryOnResponse:
    return _generate_kiosk_visual_preview_response(
        session_id=session_id,
        use_multimodal_analysis=use_multimodal_analysis,
        size=size,
        service=service,
        registry=registry,
        visual_tryon_service=visual_tryon_service,
    )


@router.post(
    "/sessions/{session_id}/try-on",
    response_model=KioskPersonalizedTryOnResponse,
    deprecated=True,
    summary="Deprecated alias for kiosk visual preview",
)
async def generate_kiosk_personalized_tryon(
    session_id: str,
    use_multimodal_analysis: bool = Query(
        default=True,
        description=(
            "Deprecated alias. Use /visual-preview when the user explicitly "
            "requests a generated preview image."
        ),
    ),
    size: str = Query(
        default="1024x1024", description="Requested generated image size"
    ),
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
    visual_tryon_service: KioskVisualTryOnService = Depends(
        get_kiosk_visual_tryon_service
    ),
) -> KioskPersonalizedTryOnResponse:
    return _generate_kiosk_visual_preview_response(
        session_id=session_id,
        use_multimodal_analysis=use_multimodal_analysis,
        size=size,
        service=service,
        registry=registry,
        visual_tryon_service=visual_tryon_service,
    )


def _generate_kiosk_visual_preview_response(
    *,
    session_id: str,
    use_multimodal_analysis: bool,
    size: str,
    service: KioskTryOnService,
    registry: GarmentRegistry,
    visual_tryon_service: KioskVisualTryOnService,
) -> KioskPersonalizedTryOnResponse:
    try:
        session = service.get_session(session_id)
        _require_capture_analysis_passed(session)
        if not session.garment_id:
            raise ValueError("garment_id is required before visual preview")

        garment = registry.get_garment(session.garment_id)
        if garment is None:
            raise FileNotFoundError(f"Garment not found: {session.garment_id}")

        result = visual_tryon_service.generate_tryon(
            session_id=session.session_id,
            garment_id=garment.garment_id,
            user_image=service.read_capture_image(
                session_id=session.session_id,
                capture_key="front",
            ),
            garment_image=registry.read_image(garment.garment_id),
            garment_category=garment.category,
            garment_type=garment.garment_type,
            use_multimodal_analysis=use_multimodal_analysis,
            size=size,
        )
        result_payload = _result_to_dict(result)
        updated_session = service.mark_personalized_tryon_ready(
            session_id=session.session_id,
            personalized_tryon_key=str(result_payload["personalized_tryon_key"]),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _personalized_tryon_response(
        updated_session,
        result,
        message="Kiosk visual preview generated",
    )


@router.post(
    "/sessions/{session_id}/fit/analyze",
    response_model=KioskFitAnalysisResponse,
)
async def analyze_kiosk_fit(
    session_id: str,
    request: KioskFitAnalysisRequest,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
    fit_service: KioskFitIntelligenceService = Depends(
        get_kiosk_fit_intelligence_service
    ),
) -> KioskFitAnalysisResponse:
    try:
        session = service.get_session(session_id)
        _require_capture_analysis_passed(session)
        if not session.garment_id:
            raise ValueError("garment_id is required before fit analysis")

        garment = registry.get_garment(session.garment_id)
        if garment is None:
            raise FileNotFoundError(f"Garment not found: {session.garment_id}")

        side_image = None
        if "side" in session.capture_keys:
            side_image = service.read_capture_image(
                session_id=session.session_id,
                capture_key="side",
            )

        result = fit_service.analyze_fit(
            session_id=session.session_id,
            garment_id=garment.garment_id,
            garment_category=garment.category,
            garment_type=garment.garment_type,
            capture_analysis=session.capture_analysis or {},
            front_image=service.read_capture_image(
                session_id=session.session_id,
                capture_key="front",
            ),
            side_image=side_image,
            garment_image=registry.read_image(garment.garment_id),
            size_chart=[
                item.model_dump(exclude_none=True) for item in request.size_chart
            ],
            preferred_fit=request.preferred_fit,
            body_measurements=(
                request.body_measurements.model_dump(exclude_none=True)
                if request.body_measurements
                else {}
            ),
            use_ai_analysis=request.use_ai_analysis,
        )
        result_payload = _result_to_dict(result)
        updated_session = service.mark_fit_analysis_ready(
            session_id=session.session_id,
            fit_analysis_key=str(result_payload["fit_analysis_key"]),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _fit_analysis_response(
        updated_session,
        result,
        message="Kiosk fit analysis generated",
    )


def _garment_record_response(record: GarmentRecord) -> KioskGarmentRecordResponse:
    return KioskGarmentRecordResponse(
        garment_id=record.garment_id,
        name=record.name,
        category=record.category,
        garment_type=record.garment_type,
        storage_provider=record.storage_provider,
        storage_uri=record.storage_uri,
        image_sha256=record.image_sha256,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
        original_filename=record.original_filename,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _personalized_tryon_response(
    session: Any,
    result: Any,
    *,
    message: str,
) -> KioskPersonalizedTryOnResponse:
    payload = _result_to_dict(result)
    return KioskPersonalizedTryOnResponse(
        success=True,
        session=_session_response(session, message="Kiosk session updated"),
        generated_image=payload.get("generated_image"),
        personalized_tryon_key=str(payload["personalized_tryon_key"]),
        personalized_tryon_path=str(payload["personalized_tryon_path"]),
        metadata_path=str(payload["metadata_path"]),
        cache_hit=bool(payload.get("cache_hit", False)),
        model=str(payload["model"]),
        prompt_version=str(payload["prompt_version"]),
        input_mapping=payload.get("input_mapping"),
        generation_time_seconds=payload.get("generation_time_seconds"),
        multimodal_analysis_applied=bool(
            payload.get("multimodal_analysis_applied", False)
        ),
        tryon_intent=payload.get("tryon_intent"),
        analyzer_model=payload.get("analyzer_model"),
        analyzer_prompt_version=payload.get("analyzer_prompt_version"),
        warnings=list(payload.get("warnings", [])),
        message=message,
    )


def _fit_analysis_response(
    session: Any,
    result: Any,
    *,
    message: str,
) -> KioskFitAnalysisResponse:
    payload = _result_to_dict(result)
    return KioskFitAnalysisResponse(
        success=True,
        session=_session_response(session, message="Kiosk session updated"),
        fit_analysis_key=str(payload["fit_analysis_key"]),
        fit_analysis_path=str(payload["fit_analysis_path"]),
        cache_hit=bool(payload.get("cache_hit", False)),
        engine_version=str(payload["engine_version"]),
        measurement_estimate=dict(payload["measurement_estimate"]),
        ai_fit_analysis=dict(payload["ai_fit_analysis"]),
        fit_assessment=dict(payload["fit_assessment"]),
        size_scores=list(payload["size_scores"]),
        size_recommendation=dict(payload["size_recommendation"]),
        fit_report=dict(payload.get("fit_report", {})),
        confidence_score=float(payload.get("confidence_score", 0.0)),
        warnings=list(payload.get("warnings", [])),
        message=message,
    )


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
        fit_analysis_key=payload.get("fit_analysis_key"),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        message=message,
    )


def _require_capture_analysis_passed(session: Any) -> None:
    payload = _result_to_dict(session)
    analysis = payload.get("capture_analysis")
    if not isinstance(analysis, dict) or analysis.get("passed") is not True:
        raise ValueError("capture analysis must pass before visual preview")


async def _read_capture_upload(
    file: UploadFile,
    *,
    field_name: str,
    max_size_bytes: int,
) -> bytes:
    image_bytes = await file.read()
    if not image_bytes:
        raise ValueError(f"{field_name} must not be empty")
    if len(image_bytes) > max_size_bytes:
        raise ValueError(f"{field_name} exceeds the configured upload limit")
    return image_bytes


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if is_dataclass(result) and not isinstance(result, type):
        return dict(vars(result))
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    raise TypeError(f"Unsupported kiosk session result type: {type(result)}")
