"""
Product ingestion endpoints.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
import httpx
import logging

from src.modules.product_ingestion.image_fetcher import ProductImageFetcher
from src.modules.product_ingestion.browser_extractor import ProductPageBrowserExtractor
from src.modules.product_ingestion.page_extractor import ProductPageExtractor
from src.schemas.requests import (
    ProductImageUrlRequest,
    ProductPageUrlRequest,
    ProductPageBrowserRequest,
    ShopeeLoginSessionRequest,
)
from src.schemas.responses import (
    ProductImageFetchResponse,
    ProductPageExtractionResponse,
    ProductExtractionErrorResponse,
    ProductImageCandidate,
    ShopeeLoginSessionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/products", tags=["products"])

image_fetcher = ProductImageFetcher()
page_extractor = ProductPageExtractor()
browser_extractor = ProductPageBrowserExtractor()


def _build_product_error_payload(
    *,
    message: str,
    extraction_mode: str | None,
) -> ProductExtractionErrorResponse:
    lowered = (message or "").lower()

    error_code = "PRODUCT_EXTRACTION_FAILED"
    requires_manual_product_image = False
    suggested_next_step = "retry"
    fallback_options: list[str] = []

    if (
        "anti-bot captcha" in lowered
        or "/verify/captcha" in lowered
        or "crawler_item" in lowered
    ):
        error_code = "SHOPEE_CAPTCHA_BLOCKED"
        requires_manual_product_image = True
        suggested_next_step = "upload_or_direct_image_url"
        fallback_options = [
            "direct_image_url",
            "upload_garment_image",
            "upload_screenshot",
        ]
    elif "still in progress" in lowered or "status=ready" in lowered:
        error_code = "SHOPEE_LOGIN_IN_PROGRESS"
        suggested_next_step = "complete_login_then_retry"
    elif "not ready" in lowered and "open-shopee-login-session" in lowered:
        error_code = "SHOPEE_LOGIN_REQUIRED"
        suggested_next_step = "open_login_session_then_retry"
    elif "only http and https" in lowered or "valid host" in lowered:
        error_code = "INVALID_PRODUCT_URL"
        suggested_next_step = "provide_valid_product_url"
    elif "did not contain an image" in lowered or "empty response" in lowered:
        error_code = "INVALID_PRODUCT_IMAGE"
        suggested_next_step = "upload_valid_image"
    elif "no product image candidates found" in lowered:
        error_code = "PRODUCT_IMAGE_NOT_FOUND"
        requires_manual_product_image = True
        suggested_next_step = "upload_or_direct_image_url"
        fallback_options = [
            "direct_image_url",
            "upload_garment_image",
            "upload_screenshot",
        ]
    elif "upstream returned 403" in lowered:
        error_code = "PRODUCT_SOURCE_FORBIDDEN"
        requires_manual_product_image = True
        suggested_next_step = "upload_or_direct_image_url"
        fallback_options = [
            "direct_image_url",
            "upload_garment_image",
            "upload_screenshot",
        ]
    elif "failed to fetch" in lowered:
        error_code = "PRODUCT_SOURCE_FETCH_FAILED"
        suggested_next_step = "retry_or_check_url"

    return ProductExtractionErrorResponse(
        error_code=error_code,
        message=message,
        requires_manual_product_image=requires_manual_product_image,
        suggested_next_step=suggested_next_step,
        fallback_options=fallback_options,
        extraction_mode=extraction_mode,
    )


def _product_error_response(
    *,
    status_code: int,
    message: str,
    extraction_mode: str | None,
) -> JSONResponse:
    payload = _build_product_error_payload(
        message=message,
        extraction_mode=extraction_mode,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
    )


async def _normalize_uploaded_product_file(
    *,
    file: UploadFile,
    source_label: str,
    success_message: str,
    extraction_mode: str,
) -> ProductImageFetchResponse | JSONResponse:
    try:
        contents = await file.read()
        result = await image_fetcher.normalize_uploaded_image(
            image_bytes=contents,
            filename=file.filename,
            content_type=file.content_type,
            source_label=source_label,
        )

        return ProductImageFetchResponse(
            success=True,
            product_image=result.image_base64,
            source_url=result.source_url,
            content_type=result.content_type,
            normalized_format=result.normalized_format,
            size_bytes=result.size_bytes,
            message=success_message,
        )
    except ValueError as e:
        return _product_error_response(
            status_code=422,
            message=str(e),
            extraction_mode=extraction_mode,
        )
    except Exception as e:
        logger.error(f"Unexpected uploaded product image ingestion failure: {e}")
        return _product_error_response(
            status_code=500,
            message=f"Product image ingestion failed: {str(e)}",
            extraction_mode=extraction_mode,
        )


@router.post("/fetch-image", response_model=ProductImageFetchResponse)
async def fetch_product_image(request: ProductImageUrlRequest):
    """
    Fetch and normalize a direct garment image URL for downstream try-on APIs.
    """
    try:
        result = await image_fetcher.fetch_image_from_url(request.image_url)

        return ProductImageFetchResponse(
            success=True,
            product_image=result.image_base64,
            source_url=result.source_url,
            content_type=result.content_type,
            normalized_format=result.normalized_format,
            size_bytes=result.size_bytes,
            message="Product image fetched and normalized successfully",
        )
    except ValueError as e:
        return _product_error_response(
            status_code=422,
            message=str(e),
            extraction_mode="direct-image",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Product image fetch failed with upstream status: {e}")
        return _product_error_response(
            status_code=422,
            message=f"Failed to fetch image URL: upstream returned {e.response.status_code}",
            extraction_mode="direct-image",
        )
    except httpx.HTTPError as e:
        logger.error(f"Product image fetch transport failed: {e}")
        return _product_error_response(
            status_code=422,
            message=f"Failed to fetch image URL: {str(e)}",
            extraction_mode="direct-image",
        )
    except Exception as e:
        logger.error(f"Unexpected product image ingestion failure: {e}")
        return _product_error_response(
            status_code=500,
            message=f"Product image ingestion failed: {str(e)}",
            extraction_mode="direct-image",
        )


@router.post("/upload-image", response_model=ProductImageFetchResponse)
async def upload_product_image(
    file: UploadFile = File(..., description="Garment image file uploaded manually"),
):
    """
    Upload and normalize a garment image file for downstream try-on APIs.
    """
    return await _normalize_uploaded_product_file(
        file=file,
        source_label="upload",
        success_message="Garment image uploaded and normalized successfully",
        extraction_mode="upload-image",
    )


@router.post("/upload-screenshot", response_model=ProductImageFetchResponse)
async def upload_product_screenshot(
    file: UploadFile = File(..., description="Screenshot containing the garment image"),
):
    """
    Upload and normalize a screenshot so the frontend can fall back from blocked sites.
    """
    return await _normalize_uploaded_product_file(
        file=file,
        source_label="screenshot",
        success_message="Screenshot uploaded and normalized successfully",
        extraction_mode="upload-screenshot",
    )


@router.post("/extract-from-page", response_model=ProductPageExtractionResponse)
async def extract_product_images_from_page(request: ProductPageUrlRequest):
    """
    Extract ranked garment image candidates from a product page URL.
    """
    try:
        result = await page_extractor.extract_from_page_url(
            page_url=request.page_url,
            max_candidates=request.max_candidates,
        )

        return ProductPageExtractionResponse(
            success=True,
            page_url=result.page_url,
            best_candidate_url=result.best_candidate_url,
            candidates=[
                ProductImageCandidate(
                    image_url=item.image_url,
                    score=item.score,
                    source=item.source,
                    reasons=item.reasons,
                )
                for item in result.candidates
            ],
            message="Product page image candidates extracted successfully",
            extraction_mode="html",
        )
    except ValueError as e:
        return _product_error_response(
            status_code=422,
            message=str(e),
            extraction_mode="html",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Product page extraction failed with upstream status: {e}")
        return _product_error_response(
            status_code=422,
            message=f"Failed to fetch product page: upstream returned {e.response.status_code}",
            extraction_mode="html",
        )
    except httpx.HTTPError as e:
        logger.error(f"Product page extraction transport failed: {e}")
        return _product_error_response(
            status_code=422,
            message=f"Failed to fetch product page: {str(e)}",
            extraction_mode="html",
        )
    except Exception as e:
        logger.error(f"Unexpected product page extraction failure: {e}")
        return _product_error_response(
            status_code=500,
            message=f"Product page extraction failed: {str(e)}",
            extraction_mode="html",
        )


@router.post("/extract-from-page-browser", response_model=ProductPageExtractionResponse)
async def extract_product_images_from_page_browser(request: ProductPageBrowserRequest):
    """
    Extract ranked garment image candidates from a product page URL using a
    persistent Playwright browser profile.
    """
    try:
        result = await browser_extractor.extract_from_page_url_browser(
            page_url=request.page_url,
            max_candidates=request.max_candidates,
            headless=request.headless,
            interactive_login=request.interactive_login,
            manual_login_timeout_seconds=request.manual_login_timeout_seconds,
        )

        return ProductPageExtractionResponse(
            success=True,
            page_url=result.page_url,
            best_candidate_url=result.best_candidate_url,
            candidates=[
                ProductImageCandidate(
                    image_url=item.image_url,
                    score=item.score,
                    source=item.source,
                    reasons=item.reasons,
                )
                for item in result.candidates
            ],
            message="Product page image candidates extracted successfully via browser",
            extraction_mode="browser",
        )
    except ValueError as e:
        return _product_error_response(
            status_code=422,
            message=str(e),
            extraction_mode="browser",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Product page extraction failed with upstream status: {e}")
        return _product_error_response(
            status_code=422,
            message=f"Failed to fetch product page: upstream returned {e.response.status_code}",
            extraction_mode="browser",
        )
    except httpx.HTTPError as e:
        logger.error(f"Product page extraction transport failed: {e}")
        return _product_error_response(
            status_code=422,
            message=f"Failed to fetch product page: {str(e)}",
            extraction_mode="browser",
        )
    except Exception as e:
        logger.error(f"Unexpected browser product page extraction failure: {e}")
        return _product_error_response(
            status_code=500,
            message=f"Browser product page extraction failed: {str(e)}",
            extraction_mode="browser",
        )


@router.post("/open-shopee-login-session", response_model=ShopeeLoginSessionResponse)
async def open_shopee_login_session(request: ShopeeLoginSessionRequest):
    """
    Open a persistent Shopee browser session so the user can log in once and
    reuse that profile for subsequent browser-based extraction.
    """
    try:
        session = await browser_extractor.open_shopee_login_session(
            page_url=request.page_url,
            manual_login_timeout_seconds=request.manual_login_timeout_seconds,
        )

        return ShopeeLoginSessionResponse(
            success=True,
            status=str(session.get("status") or "idle"),
            is_ready=bool(session.get("is_ready")),
            page_url=str(
                session.get("page_url")
                or request.page_url
                or "https://shopee.vn/buyer/login"
            ),
            final_url=session.get("final_url"),
            profile_dir=str(
                session.get("profile_dir") or browser_extractor.profile_dir
            ),
            started_at=session.get("started_at"),
            updated_at=session.get("updated_at"),
            message=str(
                session.get("message") or "Shopee login session state updated."
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected Shopee login session failure: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Shopee login session failed: {str(e)}",
        )


@router.get("/check-shopee-login-session", response_model=ShopeeLoginSessionResponse)
async def check_shopee_login_session():
    """
    Return the current status of the persistent Shopee login session.
    """
    try:
        session = browser_extractor.get_shopee_login_session_status()
        page_url = session.get("page_url") or "https://shopee.vn/buyer/login"

        return ShopeeLoginSessionResponse(
            success=True,
            status=str(session.get("status") or "idle"),
            is_ready=bool(session.get("is_ready")),
            page_url=str(page_url),
            final_url=session.get("final_url"),
            profile_dir=str(
                session.get("profile_dir") or browser_extractor.profile_dir
            ),
            started_at=session.get("started_at"),
            updated_at=session.get("updated_at"),
            message=str(
                session.get("message") or "Shopee login session status retrieved."
            ),
        )
    except Exception as e:
        logger.error(f"Unexpected Shopee login session status failure: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Shopee login session status failed: {str(e)}",
        )
