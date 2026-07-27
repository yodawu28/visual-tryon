"""
Kiosk try-on session API endpoints.
"""

from __future__ import annotations

import json
from dataclasses import is_dataclass
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi import status
from fastapi.responses import FileResponse

from src.config.settings import get_settings
from src.modules.avatar_preview.tryon_analyzer import OllamaTryOnAnalyzer
from src.modules.image_generator.local_leffa_kiosk_generator import (
    LocalLeffaKioskGenerator,
)
from src.modules.jobs.queue import JobService, LocalJobQueueBackend
from src.modules.kiosk_tryon.capture_analyzer import MediaPipeKioskCaptureAnalyzer
from src.modules.kiosk_tryon.fit_intelligence import (
    KioskFitIntelligenceService,
    OllamaFitAnalyzer,
)
from src.modules.kiosk_tryon.garment_registry import (
    GarmentRecord,
    GarmentRegistry,
    parse_size_chart_json,
)
from src.modules.kiosk_tryon.job_handlers import (
    KIOSK_VISUAL_PREVIEW_JOB_TYPE,
    KIOSK_VISUAL_PREVIEW_QUEUE,
)
from src.modules.kiosk_tryon.service import KioskTryOnService
from src.modules.kiosk_tryon.size_chart_registry import (
    SizeChartRecord,
    SizeChartRegistry,
)
from src.modules.kiosk_tryon.visual_tryon import KioskVisualTryOnService
from src.modules.kiosk_tryon.visual_preview_quality import (
    require_visual_preview_capture_ready,
)
from src.schemas.requests import (
    KioskFitAnalysisRequest,
    KioskSessionCreateRequest,
    KioskSizeChartCreateRequest,
    KioskVisualPreviewJobRequest,
)
from src.schemas.responses import (
    KioskFitAnalysisResponse,
    KioskGarmentListResponse,
    KioskGarmentRecordResponse,
    KioskGarmentResponse,
    KioskJobResponse,
    KioskPersonalizedTryOnResponse,
    KioskSessionResponse,
    KioskSizeChartListResponse,
    KioskSizeChartRecordResponse,
    KioskSizeChartResponse,
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
def get_kiosk_size_chart_registry() -> SizeChartRegistry:
    settings = get_settings()
    return SizeChartRegistry(
        db_path=settings.temp_storage_dir / "size_charts" / "size_charts.sqlite3"
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
        generator=_build_kiosk_visual_generator(settings),
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


@lru_cache
def get_kiosk_job_service() -> JobService:
    settings = get_settings()
    queue_backend = settings.job_queue_backend.strip().lower()
    if queue_backend != "local":
        raise RuntimeError(
            f"Unsupported JOB_QUEUE_BACKEND: {settings.job_queue_backend}"
        )
    return JobService(
        backend=LocalJobQueueBackend(job_dir=settings.job_queue_dir),
    )


@router.post("/garments", response_model=KioskGarmentResponse)
async def upload_kiosk_garment(
    file: UploadFile = File(..., description="Garment image file"),
    category: str = Form(
        ...,
        description="Garment category: tops, bottoms, one_pieces, full_outfit",
    ),
    name: str | None = Form(default=None, description="Optional garment display name"),
    garment_type: str | None = Form(
        default=None,
        description="Optional garment type such as jersey, t-shirt, shorts",
    ),
    size_chart_id: str | None = Form(
        default=None,
        description=(
            "Optional reusable size chart id from /api/v1/kiosk/size-charts. "
            "Use this for country/region-specific static size charts."
        ),
    ),
    size_chart_json: str | None = Form(
        default=None,
        description=(
            "Optional garment size chart JSON array. If provided, fit/analyze can "
            "use it automatically without repeating size_chart in the request body. "
            "This inline chart overrides size_chart_id and is mostly for quick tests."
        ),
    ),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
    size_chart_registry: SizeChartRegistry = Depends(get_kiosk_size_chart_registry),
) -> KioskGarmentResponse:
    settings = get_settings()
    image_bytes = await file.read()
    try:
        _validate_size_chart_id_for_garment(
            size_chart_id=size_chart_id,
            garment_category=category,
            size_chart_registry=size_chart_registry,
        )
        record = registry.create_garment(
            image_bytes=image_bytes,
            category=category,
            name=name,
            garment_type=garment_type,
            original_filename=file.filename,
            size_chart_id=size_chart_id,
            size_chart=parse_size_chart_json(size_chart_json),
            max_size_bytes=settings.max_upload_size_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return KioskGarmentResponse(
        success=True,
        garment=_garment_record_response(record),
        message="Kiosk garment uploaded",
    )


@router.post("/size-charts", response_model=KioskSizeChartResponse)
async def create_kiosk_size_chart(
    request: KioskSizeChartCreateRequest,
    registry: SizeChartRegistry = Depends(get_kiosk_size_chart_registry),
) -> KioskSizeChartResponse:
    try:
        record = registry.create_size_chart(
            name=request.name,
            country_code=request.country_code,
            region=request.region,
            category=request.category,
            garment_type=request.garment_type,
            source_type=request.source_type,
            source_url=request.source_url,
            last_verified_at=request.last_verified_at,
            size_chart=[
                item.model_dump(exclude_none=True) for item in request.size_chart
            ],
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return KioskSizeChartResponse(
        success=True,
        size_chart=_size_chart_record_response(record),
        message="Kiosk size chart created",
    )


@router.get("/size-charts", response_model=KioskSizeChartListResponse)
async def list_kiosk_size_charts(
    country_code: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    registry: SizeChartRegistry = Depends(get_kiosk_size_chart_registry),
) -> KioskSizeChartListResponse:
    try:
        records = registry.list_size_charts(
            country_code=country_code,
            category=category,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return KioskSizeChartListResponse(
        success=True,
        size_charts=[_size_chart_record_response(record) for record in records],
        count=len(records),
        message="Kiosk size charts loaded",
    )


@router.get("/size-charts/{size_chart_id}", response_model=KioskSizeChartResponse)
async def get_kiosk_size_chart(
    size_chart_id: str,
    registry: SizeChartRegistry = Depends(get_kiosk_size_chart_registry),
) -> KioskSizeChartResponse:
    record = registry.get_size_chart(size_chart_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Size chart not found: {size_chart_id}"
        )
    return KioskSizeChartResponse(
        success=True,
        size_chart=_size_chart_record_response(record),
        message="Kiosk size chart loaded",
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


@router.get("/garments/{garment_id}/image")
async def get_kiosk_garment_image(
    garment_id: str,
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
) -> Response:
    record = registry.get_garment(garment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Garment not found: {garment_id}")
    try:
        image_bytes = registry.read_image(garment_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=image_bytes, media_type=record.mime_type)


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
    capture_source: str | None = Form(
        default=None,
        description=(
            "Optional capture source metadata such as guided_mobile_web, "
            "kiosk_webcam, or file_upload."
        ),
    ),
    capture_metadata_json: str | None = Form(
        default=None,
        description=(
            "Optional JSON object with guided capture metadata, usually keyed "
            "by front/side and including burst frame selection scores."
        ),
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
            capture_source=capture_source,
            capture_metadata=_parse_capture_metadata_json(capture_metadata_json),
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


def _build_kiosk_visual_generator(settings: Any) -> Any:
    provider = _kiosk_visual_preview_provider(settings)
    if provider in {"local_leffa", "leffa"}:
        return LocalLeffaKioskGenerator(
            work_dir=settings.temp_storage_dir / "kiosk_tryons" / "leffa_work",
            leffa_root=settings.local_leffa_root,
            repo_url=settings.local_leffa_repo_url,
            model_repo_id=settings.local_leffa_model_repo_id,
            checkpoint_dir=settings.local_leffa_checkpoint_dir,
            python_executable=settings.local_leffa_python,
            hf_home=settings.local_leffa_hf_home,
            torch_home=settings.local_leffa_torch_home,
            xdg_cache_home=settings.local_leffa_xdg_cache_home,
            no_clone=bool(settings.local_leffa_no_clone),
            size=settings.local_leffa_size,
            device=settings.local_leffa_device,
            dtype=settings.local_leffa_dtype,
            vt_model_type=settings.local_leffa_vt_model_type,
            steps=int(settings.local_leffa_steps),
            guidance_scale=float(settings.local_leffa_guidance_scale),
            seed=int(settings.local_leffa_seed),
            ref_acceleration=bool(settings.local_leffa_ref_acceleration),
            repaint=bool(settings.local_leffa_repaint),
            preprocess_garment=bool(settings.local_leffa_preprocess_garment),
            timeout_seconds=int(settings.local_leffa_timeout),
        )
    raise RuntimeError(
        "Kiosk visual preview provider is disabled. Production kiosk visual "
        "preview requires the self-hosted Leffa engine. Set "
        "KIOSK_VISUAL_PREVIEW_PROVIDER=local_leffa after installing the Leffa "
        "runtime."
    )


def require_kiosk_visual_preview_enabled() -> None:
    settings = get_settings()
    provider = _kiosk_visual_preview_provider(settings)
    if provider in {"local_leffa", "leffa"}:
        return
    raise HTTPException(
        status_code=503,
        detail=(
            "Kiosk visual preview provider is disabled. Set "
            "KIOSK_VISUAL_PREVIEW_PROVIDER=local_leffa for self-hosted production "
            "preview."
        ),
    )


def _kiosk_visual_preview_provider(settings: Any) -> str:
    return (
        str(
            getattr(settings, "kiosk_visual_preview_provider", "disabled") or "disabled"
        )
        .strip()
        .lower()
    )


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
    _visual_preview_enabled: None = Depends(require_kiosk_visual_preview_enabled),
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
    "/sessions/{session_id}/visual-preview/jobs",
    response_model=KioskJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue optional kiosk visual preview job",
)
async def enqueue_kiosk_visual_preview_job(
    session_id: str,
    request: KioskVisualPreviewJobRequest,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
    registry: GarmentRegistry = Depends(get_kiosk_garment_registry),
    _visual_preview_enabled: None = Depends(require_kiosk_visual_preview_enabled),
    job_service: JobService = Depends(get_kiosk_job_service),
) -> KioskJobResponse:
    try:
        session = service.get_session(session_id)
        _require_capture_analysis_passed(session)
        _require_visual_preview_capture_ready(session)
        session_payload = _result_to_dict(session)
        garment_id = session_payload.get("garment_id")
        if not garment_id:
            raise ValueError("garment_id is required before visual preview")

        garment = registry.get_garment(str(garment_id))
        if garment is None:
            raise FileNotFoundError(f"Garment not found: {garment_id}")

        record = job_service.create_job(
            queue_name=KIOSK_VISUAL_PREVIEW_QUEUE,
            job_type=KIOSK_VISUAL_PREVIEW_JOB_TYPE,
            payload={
                "session_id": session_payload["session_id"],
                "garment_id": garment.garment_id,
                "garment_category": garment.category,
                "garment_type": garment.garment_type,
                "capture_keys": session_payload.get("capture_keys", []),
                "use_multimodal_analysis": request.use_multimodal_analysis,
                "size": request.size,
            },
            max_attempts=request.max_attempts,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _job_response(record, message="Kiosk visual preview job queued")


@router.post(
    "/sessions/{session_id}/try-on",
    response_model=KioskPersonalizedTryOnResponse,
    deprecated=True,
    include_in_schema=False,
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
    _visual_preview_enabled: None = Depends(require_kiosk_visual_preview_enabled),
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


@router.get(
    "/visual-previews/{personalized_tryon_key}/image",
    response_class=FileResponse,
    summary="Read generated kiosk visual preview image",
)
async def get_kiosk_visual_preview_image(
    personalized_tryon_key: str,
    visual_tryon_service: KioskVisualTryOnService = Depends(
        get_kiosk_visual_tryon_service
    ),
) -> FileResponse:
    try:
        image_path = visual_tryon_service.get_generated_image_path(
            personalized_tryon_key
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return FileResponse(
        image_path,
        media_type="image/png",
        filename=f"{personalized_tryon_key.replace(':', '-')}.png",
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
        _require_visual_preview_capture_ready(session)
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
    size_chart_registry: SizeChartRegistry = Depends(get_kiosk_size_chart_registry),
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
            size_chart=_resolve_fit_size_chart(
                request=request,
                garment=garment,
                size_chart_registry=size_chart_registry,
            ),
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


@router.get(
    "/sessions/{session_id}/fit/analysis",
    response_model=KioskFitAnalysisResponse,
)
async def get_kiosk_fit_analysis(
    session_id: str,
    service: KioskTryOnService = Depends(get_kiosk_tryon_service),
    fit_service: KioskFitIntelligenceService = Depends(
        get_kiosk_fit_intelligence_service
    ),
) -> KioskFitAnalysisResponse:
    try:
        session = service.get_session(session_id)
        session_payload = _result_to_dict(session)
        fit_analysis_key = session_payload.get("fit_analysis_key")
        if not fit_analysis_key:
            raise FileNotFoundError(f"Fit analysis not found for session: {session_id}")
        result = fit_service.get_analysis(str(fit_analysis_key))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _fit_analysis_response(
        session,
        result,
        message="Kiosk fit analysis loaded",
    )


@router.get("/jobs/{job_id}", response_model=KioskJobResponse)
async def get_kiosk_job(
    job_id: str,
    job_service: JobService = Depends(get_kiosk_job_service),
) -> KioskJobResponse:
    try:
        record = job_service.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _job_response(record, message="Kiosk job loaded")


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
        size_chart_id=record.size_chart_id,
        size_chart=record.size_chart,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _size_chart_record_response(
    record: SizeChartRecord,
) -> KioskSizeChartRecordResponse:
    return KioskSizeChartRecordResponse(
        size_chart_id=record.size_chart_id,
        name=record.name,
        country_code=record.country_code,
        region=record.region,
        category=record.category,
        garment_type=record.garment_type,
        source_type=record.source_type,
        source_url=record.source_url,
        last_verified_at=record.last_verified_at,
        size_chart=record.size_chart,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _resolve_fit_size_chart(
    *,
    request: KioskFitAnalysisRequest,
    garment: GarmentRecord,
    size_chart_registry: SizeChartRegistry,
) -> list[dict[str, Any]]:
    request_size_chart = [
        item.model_dump(exclude_none=True) for item in request.size_chart
    ]
    if request_size_chart:
        return request_size_chart
    if garment.size_chart:
        return garment.size_chart
    if garment.size_chart_id:
        size_chart = size_chart_registry.get_size_chart(garment.size_chart_id)
        if size_chart is None:
            raise FileNotFoundError(f"Size chart not found: {garment.size_chart_id}")
        return size_chart.size_chart
    return garment.size_chart


def _validate_size_chart_id_for_garment(
    *,
    size_chart_id: str | None,
    garment_category: str,
    size_chart_registry: SizeChartRegistry,
) -> None:
    if size_chart_id is None or not size_chart_id.strip():
        return
    size_chart = size_chart_registry.get_size_chart(size_chart_id.strip())
    if size_chart is None:
        raise FileNotFoundError(f"Size chart not found: {size_chart_id}")
    if size_chart.category != garment_category.strip().lower():
        raise ValueError(
            "size_chart_id category must match the uploaded garment category"
        )


def _job_response(record: Any, *, message: str) -> KioskJobResponse:
    payload = _result_to_dict(record)
    return KioskJobResponse(
        success=True,
        job_id=str(payload["job_id"]),
        queue_name=str(payload["queue_name"]),
        job_type=str(payload["job_type"]),
        status=str(payload["status"]),
        payload=dict(payload.get("payload", {})),
        result=payload.get("result"),
        error=payload.get("error"),
        attempts=int(payload.get("attempts", 0)),
        max_attempts=int(payload.get("max_attempts", 1)),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        message=message,
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
        output_quality_gate=payload.get("output_quality_gate"),
        generation_metadata=_dict_or_empty(payload.get("generation_metadata")),
        diagnostic_artifacts=_dict_or_empty(payload.get("diagnostic_artifacts")),
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
        confidence_breakdown=dict(payload.get("confidence_breakdown", {})),
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


def _require_visual_preview_capture_ready(session: Any) -> None:
    payload = _result_to_dict(session)
    analysis = payload.get("capture_analysis")
    if not isinstance(analysis, dict):
        raise ValueError("capture analysis must pass before visual preview")
    require_visual_preview_capture_ready(analysis)


def _parse_capture_metadata_json(value: str | None) -> dict[str, Any] | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("capture_metadata_json must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("capture_metadata_json must be a JSON object")
    return parsed


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


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
