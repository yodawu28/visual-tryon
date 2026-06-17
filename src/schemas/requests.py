"""
Request schemas cho API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional

from src.modules.avatar_preview.profile import (
    AvatarFraming,
    AvatarPreviewQualityMode,
    AvatarProfileInput,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)


class VTOAnalysisRequest(BaseModel):
    """
    Request model cho virtual try-on analysis.
    """

    anonymized_user_image: str = Field(
        ...,
        description="Base64-encoded anonymized user image (face must be replaced)",
    )
    product_image: str = Field(
        ..., description="Base64-encoded product image from Shopee or other source"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "anonymized_user_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
            }
        }


class TryOnGenerationRequest(BaseModel):
    """
    Request model cho try-on image generation với IDM-VTON.

    IDM-VTON requires both user image and garment image for visual reference.
    """

    anonymized_user_image: str = Field(
        ..., description="Base64-encoded anonymized user image"
    )
    product_image: str = Field(
        ..., description="Base64-encoded product/garment image from Shopee"
    )
    inpainting_prompt: str = Field(
        ...,
        description="Detailed prompt from semantic parser (Module 2 output) - used for category detection",
        max_length=4000,
    )
    mask: Optional[str] = Field(
        None,
        description="Optional mask (not used by IDM-VTON)",
    )
    size: str = Field(
        default="1024x1024",
        description="Output image size (IDM-VTON outputs 768x1024)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "anonymized_user_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "inpainting_prompt": "A sports jersey worn by person standing straight...",
                "mask": None,
                "size": "1024x1024",
            }
        }


class ProductImageUrlRequest(BaseModel):
    """
    Request model for direct product image URL ingestion.
    """

    image_url: str = Field(
        ...,
        description="Direct HTTP(S) URL to a garment image file",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://cdn.example.com/products/jersey-front.jpg",
            }
        }


class ProductPageUrlRequest(BaseModel):
    """
    Request model for extracting image candidates from a product page.
    """

    page_url: str = Field(
        ...,
        description="HTTP(S) product page URL containing garment images",
    )
    max_candidates: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of ranked image candidates to return",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "page_url": "https://shop.example.com/products/team-jersey",
                "max_candidates": 5,
            }
        }


class ProductPageBrowserRequest(BaseModel):
    """
    Request model for browser-based product page extraction.
    """

    page_url: str = Field(
        ...,
        description="HTTP(S) product page URL containing garment images",
    )
    max_candidates: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of ranked image candidates to return",
    )
    headless: bool = Field(
        default=True,
        description="Run browser headless for reuse after login; set false for first-time manual login",
    )
    interactive_login: bool = Field(
        default=False,
        description="Keep the browser session open so the user can log in manually if Shopee blocks access",
    )
    manual_login_timeout_seconds: int = Field(
        default=180,
        ge=30,
        le=900,
        description="How long to wait for manual login when interactive_login=true",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "page_url": "https://shopee.vn/product/123/456",
                "max_candidates": 5,
                "headless": False,
                "interactive_login": True,
                "manual_login_timeout_seconds": 180,
            }
        }


class ShopeeLoginSessionRequest(BaseModel):
    """
    Request model for opening a persistent Shopee login session.
    """

    page_url: Optional[str] = Field(
        default="https://shopee.vn/buyer/login",
        description="Shopee page to open before manual login",
    )
    manual_login_timeout_seconds: int = Field(
        default=180,
        ge=30,
        le=900,
        description="How long to wait for manual login before timing out",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "page_url": "https://shopee.vn/buyer/login",
                "manual_login_timeout_seconds": 180,
            }
        }


class ManualProductTryOnRequest(BaseModel):
    """
    Request model for end-to-end try-on using either a normalized product image
    or a direct image URL that will be fetched first.
    """

    anonymized_user_image: str = Field(
        ...,
        description="Base64-encoded anonymized user image",
    )
    product_image: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded normalized product image",
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Optional direct HTTP(S) image URL used when product_image is not provided",
    )
    mask: Optional[str] = Field(
        default=None,
        description="Optional mask passed through to the generator",
    )
    size: str = Field(
        default="1024x1024",
        description="Output image size",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "anonymized_user_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "image_url": None,
                "mask": None,
                "size": "1024x1024",
            }
        }


class AvatarPreviewAvatarRequest(BaseModel):
    """
    Request model for generating a privacy-safe synthetic avatar before try-on.
    """

    body_profile: AvatarProfileInput = Field(
        ...,
        description="Body-only profile used to generate a synthetic avatar",
    )
    garment_type: Optional[GarmentType] = Field(
        default=None,
        description="Optional garment type; when provided it determines the edit region",
    )
    garment_region: Optional[GarmentRegion] = Field(
        default=None,
        description="Optional fallback garment region when garment_type is absent or unknown",
    )
    garment_sleeve_length: Optional[GarmentSleeveLength] = Field(
        default=None,
        description="Optional sleeve context for upper-body avatar generation",
    )
    avatar_framing: Optional[AvatarFraming] = Field(
        default=None,
        description="Optional avatar framing override; use full_body for full-body shirt previews",
    )
    force_regenerate: bool = Field(
        default=False,
        description="Regenerate the avatar instead of reusing the cache entry",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "body_profile": {
                    "input_mode": "basic",
                    "basic": {
                        "gender_presentation": "male",
                        "body_build": "athletic",
                        "height_range": "tall",
                        "shoulder_width": "broad",
                        "fit_preference": "regular",
                        "pose": "front_relaxed",
                        "skin_tone": "not_specified",
                        "age_band": "adult",
                    },
                },
                "garment_type": "jersey",
                "garment_sleeve_length": "short_sleeve",
                "garment_region": "upper_body",
                "avatar_framing": "full_body",
                "force_regenerate": False,
            }
        }


class AvatarPreviewTryOnRequest(BaseModel):
    """
    Request model for applying a garment to a cached synthetic avatar.
    """

    avatar_cache_key: str = Field(
        ...,
        description="Cache key returned by /api/v1/avatar-preview/avatars",
    )
    product_image: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded normalized garment image",
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Optional direct HTTP(S) garment image URL when product_image is absent",
    )
    size: str = Field(
        default="1024x1024",
        description="Output image size requested from the preview generator",
    )
    quality_mode: AvatarPreviewQualityMode = Field(
        default=AvatarPreviewQualityMode.CREATIVE_PREVIEW,
        description=(
            "Avatar preview currently only supports creative_preview. "
            "garment_fidelity is reserved for non-avatar/provider-specific "
            "experiments and is rejected by this endpoint."
        ),
    )
    use_multimodal_analysis: bool = Field(
        default=False,
        description=(
            "When true, analyze avatar and garment with the configured multimodal "
            "analyzer before prompt building and provider routing"
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "avatar_cache_key": "avatar:v1:...",
                "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "image_url": None,
                "size": "1024x1024",
                "quality_mode": "creative_preview",
                "use_multimodal_analysis": True,
            }
        }


class KioskSessionCreateRequest(BaseModel):
    """
    Request model for creating a kiosk session.

    The default kiosk flow starts from a garment and then captures the user.
    Avatar fields are retained for advanced flows, but are not required.
    """

    garment_id: Optional[str] = Field(
        default=None,
        description="Optional product/garment identifier from the upstream catalog",
    )
    avatar_cache_key: Optional[str] = Field(
        default=None,
        description="Advanced optional synthetic avatar cache key",
    )
    avatar_preview_cache_key: Optional[str] = Field(
        default=None,
        description="Advanced optional avatar preview cache key",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "garment_id": "garment:v1:642b276d13c341e0accd8b10352b00e3",
            }
        }


class KioskVisualPreviewJobRequest(BaseModel):
    """
    Request for enqueueing an async kiosk visual preview job.
    """

    use_multimodal_analysis: bool = Field(
        default=True,
        description=(
            "Use the configured multimodal analyzer before visual preview "
            "generation when the worker executes this job."
        ),
    )
    size: str = Field(
        default="1024x1024",
        description="Requested generated image size",
    )
    max_attempts: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Maximum worker attempts for this job",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "use_multimodal_analysis": True,
                "size": "1024x1024",
                "max_attempts": 1,
            }
        }


class KioskSizeChartItem(BaseModel):
    """
    One garment size row for future fit recommendation.
    """

    size: str = Field(..., description="Display size such as S, M, L, XL")
    chest_cm: Optional[float] = Field(default=None, gt=0)
    waist_cm: Optional[float] = Field(default=None, gt=0)
    hip_cm: Optional[float] = Field(default=None, gt=0)
    shoulder_cm: Optional[float] = Field(default=None, gt=0)
    length_cm: Optional[float] = Field(default=None, gt=0)
    inseam_cm: Optional[float] = Field(default=None, gt=0)


class KioskSizeChartCreateRequest(BaseModel):
    """
    Request for creating a reusable kiosk size chart.
    """

    name: str = Field(..., description="Display name, for example Yonex VN tops")
    country_code: str = Field(
        ...,
        description="Market/country code such as VN, US, UK, EU, or JP",
        max_length=12,
    )
    region: Optional[str] = Field(
        default=None,
        description="Optional region label such as Southeast Asia",
        max_length=80,
    )
    category: str = Field(
        ...,
        description="Garment category: tops, bottoms, one_pieces, full_outfit",
    )
    garment_type: Optional[str] = Field(
        default=None,
        description="Optional garment type such as jersey, t-shirt, shorts",
        max_length=80,
    )
    source_type: Optional[str] = Field(
        default=None,
        description=(
            "Optional source label such as generic_reference, brand_official, "
            "merchant_provided, or internal"
        ),
        max_length=80,
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Optional public source URL for this chart",
        max_length=500,
    )
    last_verified_at: Optional[str] = Field(
        default=None,
        description="Optional ISO date/time when this chart was last verified",
        max_length=80,
    )
    size_chart: list[KioskSizeChartItem] = Field(
        ..., description="Reusable size chart rows for this market/category"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional internal note for this chart",
        max_length=500,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "VN regular tops",
                "country_code": "VN",
                "region": "Vietnam",
                "category": "tops",
                "garment_type": "jersey",
                "source_type": "generic_reference",
                "source_url": None,
                "last_verified_at": None,
                "size_chart": [
                    {"size": "S", "chest_cm": 90, "waist_cm": 78},
                    {"size": "M", "chest_cm": 96, "waist_cm": 84},
                    {"size": "L", "chest_cm": 102, "waist_cm": 90},
                ],
                "notes": "Default VN tops chart for kiosk testing",
            }
        }


class KioskBodyMeasurements(BaseModel):
    """
    Optional user-provided or upstream-estimated body measurements.
    """

    height_cm: Optional[float] = Field(default=None, gt=0)
    weight_kg: Optional[float] = Field(default=None, gt=0)
    chest_cm: Optional[float] = Field(default=None, gt=0)
    waist_cm: Optional[float] = Field(default=None, gt=0)
    hip_cm: Optional[float] = Field(default=None, gt=0)
    shoulder_cm: Optional[float] = Field(default=None, gt=0)
    inseam_cm: Optional[float] = Field(default=None, gt=0)


class KioskFitAnalysisRequest(BaseModel):
    """
    Request model for kiosk Fit Intelligence.

    For the normal Swagger workflow, upload the garment size chart once through
    `POST /api/v1/kiosk/garments` using `size_chart_json`, then call this
    endpoint with only body measurements and preferred fit. `size_chart` remains
    available here as an override for ad hoc tests.
    """

    preferred_fit: str = Field(
        default="regular",
        description="User preferred fit such as slim, regular, relaxed, or loose",
        max_length=40,
    )
    size_chart: list[KioskSizeChartItem] = Field(
        default_factory=list,
        description=(
            "Optional override garment size chart. If omitted, Fit Intelligence "
            "uses the size chart stored on the uploaded garment when available."
        ),
    )
    body_measurements: Optional[KioskBodyMeasurements] = Field(
        default=None,
        description=(
            "Optional body profile from user input or an upstream measurement model. "
            "For kiosk Swagger testing, height_cm and weight_kg are enough for a "
            "low-confidence estimate. Add chest/waist/hip/shoulder/inseam when "
            "available for a stronger recommendation."
        ),
    )
    use_ai_analysis: bool = Field(
        default=False,
        description=(
            "Use the configured AI fit analyzer for advisory notes only. The final "
            "size recommendation remains deterministic."
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "preferred_fit": "regular",
                "body_measurements": {
                    "height_cm": 178,
                    "weight_kg": 74,
                },
                "use_ai_analysis": False,
                "size_chart": [],
            }
        }
