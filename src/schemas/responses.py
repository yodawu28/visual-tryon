"""
Response schemas cho API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ClothingAnalysis(BaseModel):
    """
    Structured output từ VLM semantic parsing.
    """

    clothing_description: str = Field(
        ..., description="Detailed description of fabric, form, collar/sleeve details"
    )
    body_pose: str = Field(..., description="User body posture and pose description")
    inpainting_prompt: str = Field(
        ..., description="Optimized prompt for image generation API"
    )
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    additional_notes: str = Field(default="")


class PrivacyGuardResponse(BaseModel):
    """
    Response từ privacy guard anonymization endpoint.
    """

    success: bool
    faces_detected: int
    anonymized_image: Optional[str] = Field(
        None, description="Base64-encoded anonymized image"
    )
    format: str = Field(
        default="base64", description="Output format (base64 or bytesio)"
    )
    message: str


class VTOAnalysisResponse(BaseModel):
    """
    Response từ VTO analysis endpoint.
    """

    success: bool
    analysis: Optional[ClothingAnalysis] = None
    message: str


class HealthResponse(BaseModel):
    """
    Health check response.
    """

    status: str
    modules: list[str]


class TryOnGenerationResponse(BaseModel):
    """
    Response từ try-on generation endpoint.
    """

    success: bool
    generated_image: Optional[str] = Field(
        None, description="Base64-encoded generated try-on image"
    )
    message: str
    generation_time_seconds: Optional[float] = None
    generator_mode: Optional[str] = Field(
        None, description="Generator mode used (for client reference)"
    )
    is_actual_tryon: bool = Field(
        default=False,
        description="True if preserves user appearance, False if AI-generated visualization",
    )
    mask_supported: bool = Field(
        default=False,
        description="True if the active generation pipeline supports applying the provided mask",
    )
    mask_applied: bool = Field(
        default=False,
        description="True if a valid mask was actually applied in the generation pipeline",
    )
    face_preserve_applied: bool = Field(
        default=False,
        description="True if qwen-fast post-processing restored the anonymized face/head region",
    )
    face_preserve_source: Optional[str] = Field(
        default=None,
        description="Source used to locate the face region for qwen-fast post-processing",
    )
    is_preview: bool = Field(
        default=False,
        description="True when the active generation pipeline is a preview model",
    )
    replicate_model: Optional[str] = Field(
        default=None,
        description="Replicate model or version used for preview generation",
    )
    model_warning: Optional[str] = Field(
        default=None,
        description="Client-facing warning about preview model limitations",
    )


class ProductImageFetchResponse(BaseModel):
    """
    Response for direct product image URL ingestion.
    """

    success: bool
    product_image: Optional[str] = Field(
        None,
        description="Base64-encoded normalized garment image",
    )
    source_url: Optional[str] = None
    content_type: Optional[str] = None
    normalized_format: str = Field(default="jpeg")
    size_bytes: Optional[int] = None
    message: str


class ProductImageCandidate(BaseModel):
    """
    Ranked image candidate discovered on a product page.
    """

    image_url: str
    score: int
    source: str
    reasons: list[str] = Field(default_factory=list)


class ProductPageExtractionResponse(BaseModel):
    """
    Response for product page image extraction.
    """

    success: bool
    page_url: str
    best_candidate_url: Optional[str] = None
    candidates: list[ProductImageCandidate] = Field(default_factory=list)
    message: str
    extraction_mode: Optional[str] = None


class ProductExtractionErrorResponse(BaseModel):
    """
    Structured error response for product ingestion and extraction endpoints.
    """

    success: bool = False
    error_code: str
    message: str
    requires_manual_product_image: bool = False
    suggested_next_step: Optional[str] = None
    fallback_options: list[str] = Field(default_factory=list)
    extraction_mode: Optional[str] = None


class ShopeeLoginSessionResponse(BaseModel):
    """
    Response for opening a persistent Shopee login session.
    """

    success: bool
    status: str
    is_ready: bool = False
    page_url: str
    final_url: Optional[str] = None
    profile_dir: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: str


class ManualProductTryOnResponse(BaseModel):
    """
    Response for one-shot manual-product try-on orchestration.
    """

    success: bool
    analysis: Optional[ClothingAnalysis] = None
    generated_image: Optional[str] = Field(
        None,
        description="Base64-encoded generated try-on image",
    )
    message: str
    generation_time_seconds: Optional[float] = None
    generator_mode: Optional[str] = None
    is_actual_tryon: bool = False
    mask_supported: bool = False
    mask_applied: bool = False
    face_preserve_applied: bool = False
    face_preserve_source: Optional[str] = None
    is_preview: bool = False
    replicate_model: Optional[str] = None
    model_warning: Optional[str] = None
    product_source_mode: str
    product_source_url: Optional[str] = None


class FullFlowTryOnResponse(BaseModel):
    """
    Response for the full-flow try-on endpoint starting from a raw user image.
    """

    success: bool
    faces_detected: int
    anonymized_image: str = Field(
        ...,
        description="Base64-encoded anonymized user image used for downstream steps",
    )
    privacy_level_used: str
    warnings: list[str] = Field(default_factory=list)
    analysis: Optional[ClothingAnalysis] = None
    generated_image: Optional[str] = Field(
        None,
        description="Base64-encoded generated try-on image",
    )
    message: str
    generation_time_seconds: Optional[float] = None
    generator_mode: Optional[str] = None
    is_actual_tryon: bool = False
    mask_supported: bool = False
    mask_applied: bool = False
    face_preserve_applied: bool = False
    face_preserve_source: Optional[str] = None
    is_preview: bool = False
    replicate_model: Optional[str] = None
    model_warning: Optional[str] = None
    product_source_mode: str
    product_source_url: Optional[str] = None
