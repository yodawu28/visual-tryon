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
    Request model for creating a kiosk session after avatar preview approval.
    """

    garment_id: Optional[str] = Field(
        default=None,
        description="Optional product/garment identifier from the upstream catalog",
    )
    avatar_cache_key: str = Field(
        ...,
        description="Cache key returned by /api/v1/avatar-preview/avatars",
    )
    avatar_preview_cache_key: str = Field(
        ...,
        description="Cache key returned by /api/v1/avatar-preview/try-on",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "garment_id": "garment-001",
                "avatar_cache_key": "avatar:v1:...",
                "avatar_preview_cache_key": "avatar-preview:v1:...",
            }
        }


class KioskUserCaptureRequest(BaseModel):
    """
    Request model for adding webcam captures to a kiosk session.
    """

    front_image: str = Field(
        ...,
        description="Base64-encoded front-facing user capture from the kiosk webcam",
    )
    side_image: Optional[str] = Field(
        default=None,
        description="Optional base64-encoded side-facing user capture",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "front_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
                "side_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ...",
            }
        }
