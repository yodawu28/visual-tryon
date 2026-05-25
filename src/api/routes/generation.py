"""
Image Generation API endpoints.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
import base64
import cv2
import hashlib
import numpy as np
import logging
import re
import time

from src.modules.image_generator.replicate_generator import ReplicateGenerator
from src.modules.image_generator.replicate_preview_generator import (
    ReplicatePreviewGenerator,
)
from src.modules.image_generator.catvton_generator import CatVTONGenerator
from src.modules.image_generator.dalle_generator import DALLEGenerator
from src.modules.image_generator.huggingface_vton_generator import (
    HuggingFaceVTONGenerator,
)
from src.api.routes.privacy import anonymize_image_bytes
from src.modules.privacy_guard.face_anonymizer import FaceAnonymizer
from src.modules.privacy_guard.face_detector import FaceDetector
from src.modules.product_ingestion.image_fetcher import ProductImageFetcher
from src.modules.semantic_parser.openai_client import SemanticParserClient
from src.schemas.requests import TryOnGenerationRequest, ManualProductTryOnRequest
from src.schemas.responses import (
    ClothingAnalysis,
    FullFlowTryOnResponse,
    TryOnGenerationResponse,
    ManualProductTryOnResponse,
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/generate", tags=["generation"])
manual_router = APIRouter(prefix="/api/v1/tryon", tags=["generation"])


def _is_replicate_preview_mode(mode: str) -> bool:
    return mode in {"qwen-fast", "replicate-preview"}


# Initialize generator based on mode
def _get_image_generator():
    """Factory function cho image generator dựa trên config mode."""
    settings = get_settings()
    mode = settings.image_gen_mode.lower()

    if mode == "local":
        logger.info("Using LOCAL CatVTON generator (MacBook M-series)")
        return CatVTONGenerator()
    elif mode == "dalle":
        logger.info("Using DALL-E 3 generator with garment analysis")
        return DALLEGenerator()
    elif mode == "hf-vton":
        logger.info("Using HuggingFace Spaces IDM-VTON (proper visual try-on)")
        return HuggingFaceVTONGenerator()
    elif _is_replicate_preview_mode(mode):
        logger.info("Using Replicate preview generator")
        return ReplicatePreviewGenerator()
    elif mode == "remote":
        logger.info("Using REMOTE Replicate IDM-VTON generator")
        return ReplicateGenerator()
    else:
        raise ValueError(
            "Invalid IMAGE_GEN_MODE: "
            f"{mode}. Must be 'local', 'dalle', 'hf-vton', 'qwen-fast', 'replicate-preview', or 'remote'"
        )


# Singleton instance
image_generator = _get_image_generator()
manual_product_semantic_parser = SemanticParserClient()
manual_product_image_fetcher = ProductImageFetcher()
qwen_face_preserve_detector = FaceDetector()

FaceBox = tuple[int, int, int, int]


def _fingerprint_base64_payload(payload: str | None) -> str:
    if not payload:
        return "none"

    normalized = payload.strip()
    if normalized.startswith("data:"):
        parts = normalized.split("base64,", 1)
        normalized = parts[1] if len(parts) == 2 else normalized
    normalized = re.sub(r"\s+", "", normalized)

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"len={len(normalized)},sha256={digest}"


def _normalize_optional_form_value(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if normalized.lower() in {"null", "undefined", "none"}:
        return None
    return normalized


def _is_supported_base64_image(image_b64: str) -> bool:
    try:
        SemanticParserClient._prepare_openai_image_data_url(image_b64)
    except ValueError:
        return False
    return True


def _decode_base64_payload(payload: str, *, field_name: str) -> bytes:
    if not payload:
        raise ValueError(f"{field_name} payload is empty")

    normalized = payload.strip()
    if normalized.startswith("data:"):
        try:
            normalized = normalized.split("base64,", 1)[1]
        except IndexError as exc:
            raise ValueError(f"Invalid data URL {field_name} payload") from exc

    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("-", "+").replace("_", "/")
    missing_padding = len(normalized) % 4
    if missing_padding:
        normalized += "=" * (4 - missing_padding)

    try:
        return base64.b64decode(normalized, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 {field_name} payload") from exc


def _decode_image_array_from_b64(
    payload: str,
    *,
    field_name: str,
    flags: int,
) -> np.ndarray:
    image_bytes = _decode_base64_payload(payload, field_name=field_name)
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), flags)
    if image is None:
        raise ValueError(
            f"{field_name} must be a supported image (png, jpeg, gif, webp)"
        )
    return image


def _decode_mask_array(mask_b64: str) -> np.ndarray:
    mask = _decode_image_array_from_b64(
        mask_b64,
        field_name="mask",
        flags=cv2.IMREAD_GRAYSCALE,
    )

    if min(mask.shape[:2]) < 8:
        raise ValueError("mask image is too small to be valid")

    return mask


def _mask_support_for_mode(mode: str) -> bool:
    return mode == "local" or _is_replicate_preview_mode(mode)


def _replicate_preview_model_identifier() -> str | None:
    settings = get_settings()
    if not _is_replicate_preview_mode(settings.image_gen_mode.lower()):
        return None
    model_version = getattr(settings, "replicate_preview_model_version", None)
    model = getattr(
        settings,
        "replicate_preview_model",
        ReplicatePreviewGenerator.DEFAULT_MODEL,
    )
    if not isinstance(model_version, str) or not model_version.strip():
        model_version = None
    if not isinstance(model, str) or not model.strip():
        model = ReplicatePreviewGenerator.DEFAULT_MODEL
    return model_version or model


def _replicate_preview_model_warning() -> str | None:
    settings = get_settings()
    if not _is_replicate_preview_mode(settings.image_gen_mode.lower()):
        return None
    warning = getattr(settings, "replicate_preview_model_warning", None)
    if not isinstance(warning, str) or not warning.strip():
        warning = ReplicatePreviewGenerator.DEFAULT_MODEL_WARNING
    return warning


def _apply_mask_composite(
    *,
    base_image_b64: str,
    generated_image_b64: str,
    mask_b64: str,
) -> str:
    base_image = _decode_image_array_from_b64(
        base_image_b64,
        field_name="anonymized_user_image",
        flags=cv2.IMREAD_COLOR,
    )
    generated_image = _decode_image_array_from_b64(
        generated_image_b64,
        field_name="generated_image",
        flags=cv2.IMREAD_COLOR,
    )
    mask = _decode_mask_array(mask_b64)

    target_h, target_w = base_image.shape[:2]
    if generated_image.shape[:2] != (target_h, target_w):
        logger.warning(
            "Resizing generated qwen-fast output from %s to match base image size %s",
            generated_image.shape[:2],
            (target_h, target_w),
        )
        generated_image = cv2.resize(
            generated_image,
            (target_w, target_h),
            interpolation=cv2.INTER_LINEAR,
        )

    if mask.shape[:2] != (target_h, target_w):
        logger.info(
            "Resizing mask from %s to match base image size %s",
            mask.shape[:2],
            (target_h, target_w),
        )
        mask = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

    mask_float = (mask >= 128).astype(np.float32)[..., None]
    coverage = float((mask_float > 0.5).mean())
    logger.info("Applying qwen-fast mask composite (coverage=%.3f)", coverage)

    composited = generated_image.astype(np.float32) * mask_float + base_image.astype(
        np.float32
    ) * (1.0 - mask_float)
    composited = np.clip(composited, 0, 255).astype(np.uint8)

    success, buffer = cv2.imencode(".png", composited)
    if not success:
        raise ValueError("Failed to encode composited qwen-fast image")

    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _encode_mask_array(mask: np.ndarray) -> str:
    success, buffer = cv2.imencode(".png", mask)
    if not success:
        raise ValueError("Failed to encode auto upper-body mask")
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def _create_auto_upper_body_mask(base_image_b64: str) -> str:
    base_image = _decode_image_array_from_b64(
        base_image_b64,
        field_name="anonymized_user_image",
        flags=cv2.IMREAD_COLOR,
    )
    height, width = base_image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    faces = qwen_face_preserve_detector.detect_faces(base_image)
    if faces:
        face = max(
            faces,
            key=lambda detected_face: (detected_face.bbox[2] - detected_face.bbox[0])
            * (detected_face.bbox[3] - detected_face.bbox[1]),
        )
        x1, y1, x2, y2 = face.bbox.astype(int)
        face_w = max(1, x2 - x1)
        face_h = max(1, y2 - y1)
        center_x = (x1 + x2) // 2

        top = max(int(y2 + face_h * 0.18), int(height * 0.38))
        bottom = min(height - 1, max(int(y2 + face_h * 2.7), int(height * 0.82)))
        left = max(0, int(center_x - face_w * 1.8))
        right = min(width - 1, int(center_x + face_w * 1.8))
        source = "face-guided"
    else:
        top = int(height * 0.40)
        bottom = int(height * 0.86)
        left = int(width * 0.24)
        right = int(width * 0.76)
        source = "fallback"

    if bottom <= top or right <= left:
        raise ValueError("Failed to create a valid auto upper-body mask")

    points = np.array(
        [
            [int((left + right) / 2), top],
            [right, int(top + (bottom - top) * 0.18)],
            [right, bottom],
            [left, bottom],
            [left, int(top + (bottom - top) * 0.18)],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(mask, [points], 255)

    kernel_size = max(5, int(min(width, height) * 0.025) | 1)
    mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)

    coverage = float((mask > 127).mean())
    logger.info(
        "Generated auto upper-body mask for qwen-fast (source=%s, bbox=(%s,%s,%s,%s), coverage=%.3f)",
        source,
        left,
        top,
        right,
        bottom,
        coverage,
    )
    return _encode_mask_array(mask)


def _apply_face_preserve_composite(
    *,
    base_image_b64: str,
    generated_image_b64: str,
    preserve_face_bboxes: list[FaceBox] | None = None,
) -> tuple[str, bool, str | None]:
    base_image = _decode_image_array_from_b64(
        base_image_b64,
        field_name="anonymized_user_image",
        flags=cv2.IMREAD_COLOR,
    )
    generated_image = _decode_image_array_from_b64(
        generated_image_b64,
        field_name="generated_image",
        flags=cv2.IMREAD_COLOR,
    )

    target_h, target_w = base_image.shape[:2]
    if generated_image.shape[:2] != (target_h, target_w):
        logger.warning(
            "Resizing generated qwen-fast output from %s to match base image size %s for face preservation",
            generated_image.shape[:2],
            (target_h, target_w),
        )
        generated_image = cv2.resize(
            generated_image,
            (target_w, target_h),
            interpolation=cv2.INTER_LINEAR,
        )

    face_bboxes = preserve_face_bboxes or []
    face_source = "full-flow original face bbox"

    if not face_bboxes:
        faces = qwen_face_preserve_detector.detect_faces(base_image)
        face_bboxes = [tuple(face.bbox.astype(int)) for face in faces]
        face_source = "anonymized base image"

    if not face_bboxes:
        logger.warning(
            "No faces detected on anonymized base image; falling back to generated image face detection"
        )
        faces = qwen_face_preserve_detector.detect_faces(generated_image)
        face_bboxes = [tuple(face.bbox.astype(int)) for face in faces]
        face_source = "generated image"

    if not face_bboxes:
        logger.warning(
            "No faces detected on either anonymized base image or generated image; skipping qwen-fast face preservation"
        )
        success, buffer = cv2.imencode(".png", generated_image)
        if not success:
            raise ValueError("Failed to encode qwen-fast face-preserved image")
        return base64.b64encode(buffer.tobytes()).decode("utf-8"), False, None

    output = generated_image.copy()
    preserved_regions = 0

    for x1, y1, x2, y2 in face_bboxes:
        ex1, ey1, ex2, ey2 = FaceAnonymizer._expand_face_bbox(
            x1,
            y1,
            x2,
            y2,
            target_w,
            target_h,
            privacy_level="standard",
        )

        base_region = base_image[ey1:ey2, ex1:ex2]
        generated_region = output[ey1:ey2, ex1:ex2]
        if base_region.size == 0 or generated_region.size == 0:
            continue

        mask = FaceAnonymizer._create_soft_face_mask(
            width=ex2 - ex1,
            height=ey2 - ey1,
            privacy_level="standard",
        )
        blended = (
            generated_region.astype(np.float32) * (1.0 - mask)
            + base_region.astype(np.float32) * mask
        )
        output[ey1:ey2, ex1:ex2] = np.clip(blended, 0, 255).astype(np.uint8)
        preserved_regions += 1

    logger.info(
        "Applied qwen-fast anonymized face preservation to %s detected face region(s) using %s",
        preserved_regions,
        face_source,
    )

    success, buffer = cv2.imencode(".png", output)
    if not success:
        raise ValueError("Failed to encode qwen-fast face-preserved image")

    return (
        base64.b64encode(buffer.tobytes()).decode("utf-8"),
        preserved_regions > 0,
        face_source if preserved_regions > 0 else None,
    )


def _validate_tryon_size(size: str) -> None:
    valid_sizes = ["1024x1024"]
    if size not in valid_sizes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid size. Supported: {', '.join(valid_sizes)}",
        )


def _resolve_full_flow_privacy_level(requested_privacy_level: str) -> str:
    settings = get_settings()
    mode = settings.image_gen_mode.lower()

    if _is_replicate_preview_mode(mode) and requested_privacy_level != "standard":
        logger.warning(
            "[full-flow] Replicate preview currently supports privacy_level=standard only; overriding requested privacy level '%s' to 'standard'",
            requested_privacy_level,
        )
        return "standard"

    return requested_privacy_level


def _build_full_flow_warnings(
    requested_privacy_level: str, effective_privacy_level: str
) -> list[str]:
    if requested_privacy_level == effective_privacy_level:
        return []

    return [
        f"privacy_level '{requested_privacy_level}' was overridden to '{effective_privacy_level}' because Replicate preview currently supports standard only."
    ]


def _build_tryon_success_payload(
    *,
    mode: str,
    generated_image_b64: str,
    generation_time: float,
    mask_supported: bool,
    mask_applied: bool,
    face_preserve_applied: bool,
    face_preserve_source: str | None,
) -> dict:
    is_actual_tryon = mode in ["local", "hf-vton", "remote"]
    is_preview = _is_replicate_preview_mode(mode)
    replicate_model = _replicate_preview_model_identifier() if is_preview else None
    model_warning = _replicate_preview_model_warning() if is_preview else None
    message = "Try-on image generated successfully"

    if mode == "dalle":
        is_actual_tryon = False
        message = (
            "AI-generated clothing visualization. "
            "Note: Does not preserve user appearance (text-to-image mode). "
            "For actual try-on, switch to IMAGE_GEN_MODE=remote (IDM-VTON)."
        )
    elif is_preview:
        is_actual_tryon = False
        message = (
            "Preview image generated successfully. "
            f"Warning: {model_warning} "
            "Use IMAGE_GEN_MODE=remote for final actual try-on validation."
        )

    return {
        "generated_image": generated_image_b64,
        "message": message,
        "generation_time_seconds": generation_time,
        "generator_mode": mode,
        "is_actual_tryon": is_actual_tryon,
        "mask_supported": mask_supported,
        "mask_applied": mask_applied,
        "face_preserve_applied": face_preserve_applied,
        "face_preserve_source": face_preserve_source,
        "is_preview": is_preview,
        "replicate_model": replicate_model,
        "model_warning": model_warning,
    }


def _generate_tryon_payload(
    *,
    anonymized_user_image: str,
    product_image: str,
    inpainting_prompt: str,
    mask: str | None,
    size: str,
    flow_label: str | None = None,
    preserve_face_bboxes: list[FaceBox] | None = None,
) -> dict:
    start_time = time.time()
    settings = get_settings()
    mode = settings.image_gen_mode.lower()
    mask = _normalize_optional_form_value(mask)
    mask_supported = _mask_support_for_mode(mode)
    mask_applied = False
    face_preserve_applied = False
    face_preserve_source = None
    log_prefix = f"[{flow_label}] " if flow_label else ""

    logger.info(
        "%sStarting try-on generation (mode=%s, size=%s)", log_prefix, mode, size
    )
    logger.info("%sPrompt: %s...", log_prefix, inpainting_prompt[:100])
    if flow_label != "full-flow":
        logger.info("%sMask provided: %s", log_prefix, mask is not None)

    _validate_tryon_size(size)

    if _is_replicate_preview_mode(mode) and mask is not None:
        _decode_mask_array(mask)
        logger.info("%sValidated Replicate preview mask input successfully", log_prefix)

    generated_image_b64 = image_generator.generate_tryon_from_b64(
        base_image_b64=anonymized_user_image,
        garment_image_b64=product_image,
        inpainting_prompt=inpainting_prompt,
        mask_b64=mask,
        size=size,
    )

    if _is_replicate_preview_mode(mode) and mask is not None:
        generated_image_b64 = _apply_mask_composite(
            base_image_b64=anonymized_user_image,
            generated_image_b64=generated_image_b64,
            mask_b64=mask,
        )
        mask_applied = True

    if _is_replicate_preview_mode(mode):
        (
            generated_image_b64,
            face_preserve_applied,
            face_preserve_source,
        ) = _apply_face_preserve_composite(
            base_image_b64=anonymized_user_image,
            generated_image_b64=generated_image_b64,
            preserve_face_bboxes=preserve_face_bboxes,
        )

    generation_time = time.time() - start_time
    if flow_label == "full-flow":
        logger.info(
            "%sTry-on generation completed (mode=%s, duration=%.2fs)",
            log_prefix,
            mode,
            generation_time,
        )
    else:
        logger.info(
            "%sTry-on generation completed (mode=%s, duration=%.2fs, mask_supported=%s, mask_applied=%s)",
            log_prefix,
            mode,
            generation_time,
            mask_supported,
            mask_applied,
        )
    return _build_tryon_success_payload(
        mode=mode,
        generated_image_b64=generated_image_b64,
        generation_time=generation_time,
        mask_supported=mask_supported,
        mask_applied=mask_applied,
        face_preserve_applied=face_preserve_applied,
        face_preserve_source=face_preserve_source,
    )


async def _run_manual_product_tryon_flow(
    *,
    anonymized_user_image: str,
    product_image: str | None,
    image_url: str | None,
    mask: str | None,
    size: str,
    flow_label: str,
    step_product_source: str,
    step_analysis: str,
    step_generation: str,
    preserve_face_bboxes: list[FaceBox] | None = None,
) -> dict:
    logger.info(
        "[%s] %s resolving product source (image_url_present=%s, product_image_fingerprint=%s)",
        flow_label,
        step_product_source,
        bool(_normalize_optional_form_value(image_url)),
        _fingerprint_base64_payload(product_image),
    )

    product_source_mode, product_source_url, product_image_b64 = (
        await _resolve_manual_product_source(
            product_image=product_image,
            image_url=image_url,
        )
    )

    logger.info(
        "[%s] %s product source resolved (source=%s, source_url=%s, product_image_fingerprint=%s)",
        flow_label,
        step_product_source,
        product_source_mode,
        product_source_url,
        _fingerprint_base64_payload(product_image_b64),
    )

    logger.info(
        "[%s] %s running vto-context (user_image_fingerprint=%s, product_image_fingerprint=%s)",
        flow_label,
        step_analysis,
        _fingerprint_base64_payload(anonymized_user_image),
        _fingerprint_base64_payload(product_image_b64),
    )
    analysis: ClothingAnalysis = manual_product_semantic_parser.analyze_vto_context(
        user_image_b64=anonymized_user_image,
        product_image_b64=product_image_b64,
    )
    logger.info(
        "[%s] %s vto-context completed (confidence=%.3f, clothing_description=%s, body_pose=%s)",
        flow_label,
        step_analysis,
        analysis.confidence_score,
        analysis.clothing_description,
        analysis.body_pose,
    )
    logger.info("[%s] Inpainting prompt: %s", flow_label, analysis.inpainting_prompt)

    if flow_label == "full-flow":
        logger.info(
            "[%s] %s running try-on (size=%s)", flow_label, step_generation, size
        )
    else:
        logger.info(
            "[%s] %s running try-on (mask_present=%s, mask_fingerprint=%s, size=%s)",
            flow_label,
            step_generation,
            mask is not None,
            _fingerprint_base64_payload(mask),
            size,
        )
    generation_payload = _generate_tryon_payload(
        anonymized_user_image=anonymized_user_image,
        product_image=product_image_b64,
        inpainting_prompt=analysis.inpainting_prompt,
        mask=mask,
        size=size,
        flow_label=flow_label,
        preserve_face_bboxes=preserve_face_bboxes,
    )

    return {
        "analysis": analysis,
        "product_source_mode": product_source_mode,
        "product_source_url": product_source_url,
        "generation_payload": generation_payload,
    }


async def _run_full_flow_tryon_chain(
    *,
    user_file: UploadFile,
    product_image: str | None,
    image_url: str | None,
    privacy_level: str,
    size: str,
) -> dict:
    logger.info(
        "[full-flow] Step 1/4: anonymizing uploaded user image (privacy=%s)",
        privacy_level,
    )
    (
        anonymized_user_image,
        faces_detected,
        original_face_bboxes,
    ) = await _anonymize_uploaded_user_image(
        file=user_file,
        privacy_level=privacy_level,
    )
    logger.info(
        "[full-flow] Anonymization completed (privacy=%s, faces_detected=%s, original_face_bboxes=%s, anonymized_image_fingerprint=%s)",
        privacy_level,
        faces_detected,
        len(original_face_bboxes),
        _fingerprint_base64_payload(anonymized_user_image),
    )

    logger.info(
        "[full-flow] Continuing with normalized product input -> vto-context -> try-on",
    )
    flow_result = await _run_manual_product_tryon_flow(
        anonymized_user_image=anonymized_user_image,
        product_image=product_image,
        image_url=image_url,
        mask=None,
        size=size,
        flow_label="full-flow",
        step_product_source="Step 2/4:",
        step_analysis="Step 3/4:",
        step_generation="Step 4/4:",
        preserve_face_bboxes=original_face_bboxes,
    )
    return {
        "faces_detected": faces_detected,
        "anonymized_user_image": anonymized_user_image,
        **flow_result,
    }


async def _resolve_manual_product_source(
    *,
    product_image: str | None,
    image_url: str | None,
) -> tuple[str, str | None, str]:
    product_image = _normalize_optional_form_value(product_image)
    image_url = _normalize_optional_form_value(image_url)

    if product_image and _is_supported_base64_image(product_image):
        return ("product_image", None, product_image)

    if product_image and image_url:
        logger.warning(
            "Ignoring invalid product_image form value and falling back to image_url"
        )

    if image_url:
        fetched_image = await manual_product_image_fetcher.fetch_image_from_url(
            image_url
        )
        return ("image_url", fetched_image.source_url, fetched_image.image_base64)

    if product_image:
        raise HTTPException(
            status_code=422,
            detail="product_image must be a supported base64 image (png, jpeg, gif, webp)",
        )

    raise HTTPException(
        status_code=422,
        detail="Provide product_image or image_url for try-on.",
    )


async def _anonymize_uploaded_user_image(
    *,
    file: UploadFile,
    privacy_level: str,
) -> tuple[str, int, list[FaceBox]]:
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Invalid image file")

    detected_faces = qwen_face_preserve_detector.detect_faces(image)
    original_face_bboxes = [
        tuple(int(value) for value in face.bbox.astype(int)) for face in detected_faces
    ]

    anonymized_b64, face_count, _ = anonymize_image_bytes(
        image_bytes=contents,
        privacy_level=privacy_level,
    )
    return anonymized_b64, face_count, original_face_bboxes


@router.post("/tryon", response_model=TryOnGenerationResponse)
async def generate_tryon_image(request: TryOnGenerationRequest):
    """
    Generate virtual try-on image using the configured backend.

    **Mode Selection** (via IMAGE_GEN_MODE env var):
    - `local`: CatVTON trên MacBook M-series với MPS backend
    - `remote`: Replicate IDM-VTON for actual try-on
    - `qwen-fast`: Replicate Qwen preview edit using user + garment references

    **Workflow**:
    1. Receive user image + mask + prompt từ Module 2 semantic analysis
    2. Call the configured image generator based on mode
    3. Return generated try-on image

    **Requirements**:
    - anonymized_user_image: Base64 encoded user image (face anonymized)
    - mask: Base64 encoded mask (white = edit area, black = keep)
    - inpainting_prompt: Semantic description từ Module 2
    - Valid size: 1024x1024

    **Returns**:
    - generated_image: Base64-encoded try-on result
    - generation_time_seconds: Generation duration
    """
    try:
        payload = _generate_tryon_payload(
            anonymized_user_image=request.anonymized_user_image,
            product_image=request.product_image,
            inpainting_prompt=request.inpainting_prompt,
            mask=request.mask,
            size=request.size,
        )
        return TryOnGenerationResponse(success=True, **payload)

    except ValueError as e:
        # Generator-specific errors
        error_msg = str(e)
        logger.error(f"Image generation failed: {error_msg}")

        # If HF Space unavailable, suggest fallback
        if "HuggingFace Space unavailable" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"{error_msg}. Try IMAGE_GEN_MODE=qwen-fast for preview fallback.",
            )

        raise HTTPException(status_code=422, detail=error_msg)
    except Exception as e:
        logger.error(f"Unexpected error during generation: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Image generation failed: {str(e)}"
        )


@manual_router.post("/manual-product", response_model=ManualProductTryOnResponse)
async def generate_tryon_from_manual_product(request: ManualProductTryOnRequest):
    """
    One-shot manual-product try-on orchestration.

    Product source priority:
    1. product_image (already normalized base64)
    2. image_url (fetch and normalize first)
    """
    try:
        logger.info(
            "[manual-product] Step 0/4: starting orchestration (user_image_fingerprint=%s, image_url_present=%s, product_image_fingerprint=%s, mask_fingerprint=%s)",
            _fingerprint_base64_payload(request.anonymized_user_image),
            bool(_normalize_optional_form_value(request.image_url)),
            _fingerprint_base64_payload(request.product_image),
            _fingerprint_base64_payload(request.mask),
        )
        flow_result = await _run_manual_product_tryon_flow(
            anonymized_user_image=request.anonymized_user_image,
            product_image=request.product_image,
            image_url=request.image_url,
            mask=request.mask,
            size=request.size,
            flow_label="manual-product",
            step_product_source="Step 1/3:",
            step_analysis="Step 2/3:",
            step_generation="Step 3/3:",
        )

        return ManualProductTryOnResponse(
            success=True,
            analysis=flow_result["analysis"],
            product_source_mode=flow_result["product_source_mode"],
            product_source_url=flow_result["product_source_url"],
            **flow_result["generation_payload"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Manual-product try-on failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during manual-product try-on: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Manual-product try-on failed: {str(e)}",
        )


@manual_router.post("/full-flow", response_model=FullFlowTryOnResponse)
async def generate_tryon_full_flow(
    user_file: UploadFile = File(..., description="Raw user image to anonymize first"),
    product_image: str | None = Form(
        default=None,
        description="Optional base64-encoded normalized product image",
    ),
    image_url: str | None = Form(
        default=None,
        description="Optional direct HTTP(S) product image URL",
    ),
    privacy_level: str = Form(
        default="standard",
        description="Privacy level used for anonymization: standard, strong, extreme",
    ),
    size: str = Form(
        default="1024x1024",
        description="Output image size",
    ),
):
    """
    End-to-end full flow:
    1. anonymize raw user image
    2. normalize product source
    3. run vto-context
    4. run try-on
    """
    try:
        effective_privacy_level = _resolve_full_flow_privacy_level(privacy_level)
        warnings = _build_full_flow_warnings(
            requested_privacy_level=privacy_level,
            effective_privacy_level=effective_privacy_level,
        )
        logger.info(
            "[full-flow] Step 0/4: starting orchestration (privacy=%s, image_url_present=%s, product_image_fingerprint=%s)",
            effective_privacy_level,
            bool(_normalize_optional_form_value(image_url)),
            _fingerprint_base64_payload(product_image),
        )
        flow_result = await _run_full_flow_tryon_chain(
            user_file=user_file,
            product_image=product_image,
            image_url=image_url,
            privacy_level=effective_privacy_level,
            size=size,
        )

        return FullFlowTryOnResponse(
            success=True,
            faces_detected=flow_result["faces_detected"],
            anonymized_image=flow_result["anonymized_user_image"],
            privacy_level_used=effective_privacy_level,
            warnings=warnings,
            analysis=flow_result["analysis"],
            product_source_mode=flow_result["product_source_mode"],
            product_source_url=flow_result["product_source_url"],
            **flow_result["generation_payload"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Full-flow try-on failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during full-flow try-on: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Full-flow try-on failed: {str(e)}",
        )
