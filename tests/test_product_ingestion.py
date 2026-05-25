"""
Tests for direct product image URL ingestion.
"""

from unittest.mock import AsyncMock, patch
from unittest.mock import Mock

import pytest
import httpx

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.products import router
from src.modules.product_ingestion.image_fetcher import (
    ProductImageFetcher,
    ProductImageResult,
)
from src.modules.product_ingestion.page_extractor import (
    ProductPageExtractor,
    ProductPageExtractionResult,
    ProductPageImageCandidate,
)
from src.modules.product_ingestion.browser_extractor import ProductPageBrowserExtractor


class TestProductImageFetcher:
    def test_validate_url_rejects_non_http_scheme(self):
        try:
            ProductImageFetcher._validate_url("ftp://example.com/image.jpg")
            assert False, "Expected ValueError for non-http scheme"
        except ValueError as exc:
            assert "http and https" in str(exc)

    def test_validate_url_rejects_missing_host(self):
        try:
            ProductImageFetcher._validate_url("https:///image.jpg")
            assert False, "Expected ValueError for missing host"
        except ValueError as exc:
            assert "valid host" in str(exc)


class TestProductRoute:
    def setup_method(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_fetch_product_image_success(self):
        mock_result = ProductImageResult(
            source_url="https://cdn.example.com/jersey.jpg",
            content_type="image/jpeg",
            image_base64="ZmFrZV9pbWFnZQ==",
            normalized_format="jpeg",
            size_bytes=1234,
        )

        with patch(
            "src.api.routes.products.image_fetcher.fetch_image_from_url",
            new=AsyncMock(return_value=mock_result),
        ):
            response = self.client.post(
                "/api/v1/products/fetch-image",
                json={"image_url": "https://cdn.example.com/jersey.jpg"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["product_image"] == "ZmFrZV9pbWFnZQ=="
        assert payload["source_url"] == "https://cdn.example.com/jersey.jpg"
        assert payload["normalized_format"] == "jpeg"

    def test_fetch_product_image_validation_error(self):
        with patch(
            "src.api.routes.products.image_fetcher.fetch_image_from_url",
            new=AsyncMock(
                side_effect=ValueError("Only http and https image URLs are supported")
            ),
        ):
            response = self.client.post(
                "/api/v1/products/fetch-image",
                json={"image_url": "ftp://example.com/jersey.jpg"},
            )

        assert response.status_code == 422
        payload = response.json()
        assert payload["success"] is False
        assert payload["error_code"] == "INVALID_PRODUCT_URL"
        assert payload["suggested_next_step"] == "provide_valid_product_url"
        assert payload["fallback_options"] == []
        assert payload["extraction_mode"] == "direct-image"

    def test_upload_product_image_success(self):
        mock_result = ProductImageResult(
            source_url="upload://garment.jpg",
            content_type="image/jpeg",
            image_base64="ZmFrZV9pbWFnZQ==",
            normalized_format="jpeg",
            size_bytes=1234,
        )

        with patch(
            "src.api.routes.products.image_fetcher.normalize_uploaded_image",
            new=AsyncMock(return_value=mock_result),
        ):
            response = self.client.post(
                "/api/v1/products/upload-image",
                files={"file": ("garment.jpg", b"fake-image", "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["product_image"] == "ZmFrZV9pbWFnZQ=="
        assert payload["source_url"] == "upload://garment.jpg"
        assert (
            payload["message"] == "Garment image uploaded and normalized successfully"
        )

    def test_upload_product_screenshot_success(self):
        mock_result = ProductImageResult(
            source_url="screenshot://product-shot.png",
            content_type="image/png",
            image_base64="ZmFrZV9pbWFnZQ==",
            normalized_format="jpeg",
            size_bytes=1200,
        )

        with patch(
            "src.api.routes.products.image_fetcher.normalize_uploaded_image",
            new=AsyncMock(return_value=mock_result),
        ):
            response = self.client.post(
                "/api/v1/products/upload-screenshot",
                files={"file": ("product-shot.png", b"fake-image", "image/png")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["source_url"] == "screenshot://product-shot.png"
        assert payload["message"] == "Screenshot uploaded and normalized successfully"

    def test_upload_product_image_validation_error(self):
        with patch(
            "src.api.routes.products.image_fetcher.normalize_uploaded_image",
            new=AsyncMock(
                side_effect=ValueError(
                    "Source did not contain an image. Content-Type was 'text/plain'"
                )
            ),
        ):
            response = self.client.post(
                "/api/v1/products/upload-image",
                files={"file": ("note.txt", b"not-an-image", "text/plain")},
            )

        assert response.status_code == 422
        payload = response.json()
        assert payload["success"] is False
        assert payload["error_code"] == "INVALID_PRODUCT_IMAGE"
        assert payload["suggested_next_step"] == "upload_valid_image"
        assert payload["extraction_mode"] == "upload-image"

    def test_extract_product_images_from_page_success(self):
        mock_result = ProductPageExtractionResult(
            page_url="https://shop.example.com/products/team-jersey",
            best_candidate_url="https://cdn.example.com/images/jersey-main.jpg",
            candidates=[
                ProductPageImageCandidate(
                    image_url="https://cdn.example.com/images/jersey-main.jpg",
                    score=140,
                    source="og:image",
                    reasons=["Open Graph image", "product/gallery hint"],
                ),
                ProductPageImageCandidate(
                    image_url="https://cdn.example.com/images/jersey-side.jpg",
                    score=80,
                    source="img",
                    reasons=["HTML image tag"],
                ),
            ],
        )

        with patch(
            "src.api.routes.products.page_extractor.extract_from_page_url",
            new=AsyncMock(return_value=mock_result),
        ):
            response = self.client.post(
                "/api/v1/products/extract-from-page",
                json={
                    "page_url": "https://shop.example.com/products/team-jersey",
                    "max_candidates": 5,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert (
            payload["best_candidate_url"]
            == "https://cdn.example.com/images/jersey-main.jpg"
        )
        assert len(payload["candidates"]) == 2
        assert payload["candidates"][0]["source"] == "og:image"
        assert payload["extraction_mode"] == "html"

    def test_extract_product_images_from_page_browser_success(self):
        mock_result = ProductPageExtractionResult(
            page_url="https://shop.example.com/products/team-jersey",
            best_candidate_url="https://cdn.example.com/images/jersey-main.jpg",
            candidates=[
                ProductPageImageCandidate(
                    image_url="https://cdn.example.com/images/jersey-main.jpg",
                    score=170,
                    source="browser-dom",
                    reasons=["browser DOM image"],
                )
            ],
        )

        with patch(
            "src.api.routes.products.browser_extractor.extract_from_page_url_browser",
            new=AsyncMock(return_value=mock_result),
        ):
            response = self.client.post(
                "/api/v1/products/extract-from-page-browser",
                json={
                    "page_url": "https://shop.example.com/products/team-jersey",
                    "max_candidates": 5,
                    "headless": False,
                    "interactive_login": True,
                    "manual_login_timeout_seconds": 180,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["extraction_mode"] == "browser"
        assert payload["candidates"][0]["source"] == "browser-dom"

    def test_extract_product_images_from_page_browser_structured_captcha_error(self):
        with patch(
            "src.api.routes.products.browser_extractor.extract_from_page_url_browser",
            new=AsyncMock(
                side_effect=ValueError(
                    "Shopee returned an anti-bot CAPTCHA challenge for this page. "
                    "Backend browser extraction cannot continue until the CAPTCHA is solved "
                    "manually in the opened browser session. If Shopee keeps re-challenging, "
                    "use /api/v1/products/fetch-image with a direct product image URL or "
                    "upload/select the garment image manually."
                )
            ),
        ):
            response = self.client.post(
                "/api/v1/products/extract-from-page-browser",
                json={
                    "page_url": "https://shopee.vn/product/123",
                    "max_candidates": 5,
                    "headless": True,
                    "interactive_login": False,
                    "manual_login_timeout_seconds": 180,
                },
            )

        assert response.status_code == 422
        payload = response.json()
        assert payload["success"] is False
        assert payload["error_code"] == "SHOPEE_CAPTCHA_BLOCKED"
        assert payload["requires_manual_product_image"] is True
        assert payload["suggested_next_step"] == "upload_or_direct_image_url"
        assert payload["fallback_options"] == [
            "direct_image_url",
            "upload_garment_image",
            "upload_screenshot",
        ]
        assert payload["extraction_mode"] == "browser"

    def test_open_shopee_login_session_success(self):
        with patch(
            "src.api.routes.products.browser_extractor.open_shopee_login_session",
            new=AsyncMock(
                return_value={
                    "status": "pending",
                    "is_ready": False,
                    "page_url": "https://shopee.vn/buyer/login",
                    "final_url": None,
                    "profile_dir": "/tmp/playwright/profile",
                    "started_at": "2026-05-15T10:00:00+00:00",
                    "updated_at": "2026-05-15T10:00:00+00:00",
                    "message": "Shopee login browser is starting.",
                }
            ),
        ):
            response = self.client.post(
                "/api/v1/products/open-shopee-login-session",
                json={
                    "page_url": "https://shopee.vn/buyer/login",
                    "manual_login_timeout_seconds": 180,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "pending"
        assert payload["is_ready"] is False
        assert payload["page_url"] == "https://shopee.vn/buyer/login"
        assert payload["profile_dir"] == "/tmp/playwright/profile"

    def test_check_shopee_login_session_success(self):
        with patch(
            "src.api.routes.products.browser_extractor.get_shopee_login_session_status",
            return_value={
                "status": "ready",
                "is_ready": True,
                "page_url": "https://shopee.vn/buyer/login",
                "final_url": "https://shopee.vn/",
                "profile_dir": "/tmp/playwright/profile",
                "started_at": "2026-05-15T10:00:00+00:00",
                "updated_at": "2026-05-15T10:01:00+00:00",
                "message": "Shopee login session is ready.",
            },
        ):
            response = self.client.get("/api/v1/products/check-shopee-login-session")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "ready"
        assert payload["is_ready"] is True
        assert payload["final_url"] == "https://shopee.vn/"


class TestProductPageExtractor:
    def test_extract_shopee_ids_from_page_url(self):
        ids = ProductPageExtractor._extract_shopee_ids_from_page_url(
            "https://shopee.vn/Ao-thun-i.1164563418.26738679642"
        )

        assert ids == ("1164563418", "26738679642")

    def test_extract_candidates_from_html_ignores_meta_without_name_or_property(self):
        html = """
        <html>
          <head>
            <meta charset="utf-8" />
            <meta content="viewport-width=device-width" />
            <meta property="og:image" content="/images/jersey-main.jpg" />
          </head>
        </html>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shop.example.com/products/team-jersey",
            html=html,
            max_candidates=5,
        )

        assert (
            result.best_candidate_url
            == "https://shop.example.com/images/jersey-main.jpg"
        )
        assert len(result.candidates) == 1

    def test_extract_candidates_from_html_ranks_meta_and_resolves_relative_urls(self):
        html = """
        <html>
          <head>
            <meta property="og:image" content="/images/jersey-main.jpg" />
            <meta name="twitter:image" content="https://cdn.example.com/images/jersey-twitter.jpg" />
          </head>
          <body>
            <img src="/assets/logo.png" alt="brand logo" width="64" height="64" />
            <img src="/images/jersey-side.jpg" alt="team jersey product image" class="product gallery" width="1200" height="1200" />
          </body>
        </html>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shop.example.com/products/team-jersey",
            html=html,
            max_candidates=5,
        )

        assert (
            result.best_candidate_url
            == "https://shop.example.com/images/jersey-main.jpg"
        )
        assert len(result.candidates) >= 2
        assert result.candidates[0].source in {"og:image", "twitter:image"}
        assert all(item.image_url.startswith("http") for item in result.candidates)

    def test_extract_candidates_from_html_penalizes_logo_assets(self):
        html = """
        <html>
          <body>
            <img src="/static/logo.png" alt="logo" width="500" height="500" />
            <img src="/images/dress-main.jpg" alt="evening dress product" width="1200" height="1600" />
          </body>
        </html>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shop.example.com/products/evening-dress",
            html=html,
            max_candidates=5,
        )

        assert (
            result.best_candidate_url
            == "https://shop.example.com/images/dress-main.jpg"
        )
        assert result.candidates[0].score > result.candidates[1].score

    def test_extract_candidates_from_raw_html_finds_shopee_style_script_urls(self):
        html = r"""
        <html>
          <body>
            <script>
              window.__INITIAL_STATE__ = {
                "images": [
                  "https:\/\/down-vn.img.susercontent.com\/file\/vn-11134207-7ras8-mainimage",
                  "https:\/\/down-vn.img.susercontent.com\/file\/vn-11134207-7ras8-sideimage"
                ]
              };
            </script>
          </body>
        </html>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shopee.vn/product/123",
            html=html,
            max_candidates=5,
        )

        assert result.best_candidate_url is not None
        assert "img.susercontent.com/file/" in result.best_candidate_url
        assert len(result.candidates) >= 2
        assert result.candidates[0].source in {"raw-html", "shopee-image-id"}

    def test_extract_candidates_from_html_prefers_shopee_images_array_over_root_host(
        self,
    ):
        html = r"""
        <html>
          <body>
            <script>
              window.__INITIAL_STATE__ = {
                "images": ["vn-11134207-7ras8-mainimagehash", "vn-11134207-7ras8-sideimagehash"],
                "cdn": "https:\/\/down-vn.img.susercontent.com\/"
              };
            </script>
          </body>
        </html>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shopee.vn/product/123",
            html=html,
            max_candidates=5,
        )

        assert (
            result.best_candidate_url
            == "https://down-vn.img.susercontent.com/file/vn-11134207-7ras8-mainimagehash"
        )
        assert result.candidates[0].source == "shopee-image-id"
        assert all(
            item.image_url != "https://down-vn.img.susercontent.com/"
            for item in result.candidates
        )

    def test_extract_candidates_from_html_rejects_shopee_splash_assets(self):
        html = """
        <html>
          <body>
            <script>
              const assets = [
                "https://deo.shopeemobile.com/shopee/shopee-mobilemall-live-sg/assets/ios_splash_screen_1080x2340.7f2707911dd441d0bc423e07da537b8c.png"
              ];
            </script>
          </body>
        </html>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shopee.vn/product/123",
            html=html,
            max_candidates=5,
        )

        assert result.best_candidate_url is None
        assert result.candidates == []

    def test_extract_shopee_image_urls_from_raw_html_supports_single_image_key(self):
        html = r"""
        <script>
          window.__INITIAL_STATE__ = {
            "thumbnail":"vn-11134207-7ras8-mainimagehash"
          };
        </script>
        """

        result = ProductPageExtractor.extract_candidates_from_html(
            page_url="https://shopee.vn/product/123",
            html=html,
            max_candidates=5,
        )

        assert (
            result.best_candidate_url
            == "https://down-vn.img.susercontent.com/file/vn-11134207-7ras8-mainimagehash"
        )

    @pytest.mark.asyncio
    async def test_extract_from_shopee_item_api_maps_images(self):
        extractor = ProductPageExtractor()

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(
            return_value={
                "error": None,
                "data": {
                    "images": [
                        "vn-11134207-7ras8-mainimagehash",
                        "vn-11134207-7ras8-sideimagehash",
                    ]
                },
            }
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "src.modules.product_ingestion.page_extractor.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await extractor._extract_from_shopee_item_api(
                page_url="https://shopee.vn/Ao-thun-i.1164563418.26738679642",
                max_candidates=5,
            )

        assert result is not None
        assert (
            result.best_candidate_url
            == "https://down-vn.img.susercontent.com/file/vn-11134207-7ras8-mainimagehash"
        )
        assert result.candidates[0].source == "shopee-api"

    @pytest.mark.asyncio
    async def test_extract_from_page_url_surfaces_shopee_403_as_value_error(self):
        extractor = ProductPageExtractor()

        mock_page_response = Mock()
        mock_page_response.raise_for_status = Mock()
        mock_page_response.headers = {"content-type": "text/html"}
        mock_page_response.text = "<html></html>"

        request = httpx.Request(
            "GET",
            "https://shopee.vn/api/v4/item/get?itemid=26738679642&shopid=1164563418",
        )
        api_response = httpx.Response(403, request=request)
        api_error = httpx.HTTPStatusError(
            "403 Forbidden",
            request=request,
            response=api_response,
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_page_response, api_error])
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "src.modules.product_ingestion.page_extractor.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(
                ValueError,
                match="Shopee blocked the item API fallback with 403 Forbidden",
            ):
                await extractor.extract_from_page_url(
                    page_url="https://shopee.vn/Ao-thun-i.1164563418.26738679642",
                    max_candidates=5,
                )


class TestProductPageBrowserExtractor:
    def test_is_shopee_blocked_detects_verify_page(self):
        assert ProductPageBrowserExtractor._is_shopee_blocked(
            "https://shopee.vn/verify/traffic/error",
            "Shopee Việt Nam | Hot Deals, Best Prices",
            "Page Unavailable Please log in and try again",
        )

    def test_is_shopee_blocked_detects_captcha_challenge(self):
        assert ProductPageBrowserExtractor._is_shopee_blocked(
            "https://shopee.vn/verify/captcha?scene=crawler_item&anti_bot=1",
            "Shopee CAPTCHA",
            "Please complete CAPTCHA verification",
        )

    def test_build_shopee_blocked_message_for_captcha_mentions_manual_fallback(self):
        message = ProductPageBrowserExtractor._build_shopee_blocked_message(
            "https://shopee.vn/verify/captcha?scene=crawler_item&anti_bot=1",
            "Shopee CAPTCHA",
            "Please complete CAPTCHA verification",
        )

        assert "anti-bot CAPTCHA" in message
        assert "/api/v1/products/fetch-image" in message

    def test_get_shopee_login_session_status_defaults_to_idle(self):
        extractor = ProductPageBrowserExtractor()

        status = extractor.get_shopee_login_session_status()

        assert status["status"] == "idle"
        assert status["is_ready"] is False

    def test_is_shopee_page_url(self):
        assert ProductPageBrowserExtractor.is_shopee_page_url(
            "https://shopee.vn/product/123"
        )
        assert not ProductPageBrowserExtractor.is_shopee_page_url(
            "https://example.com/product/123"
        )

    def test_is_shopee_login_required_detects_login_page(self):
        assert ProductPageBrowserExtractor._is_shopee_login_required(
            "https://shopee.vn/buyer/login",
            "Shopee Việt Nam | Hot Deals, Best Prices",
            "Đăng nhập vào Shopee",
        )

    def test_is_shopee_login_required_detects_qr_or_sms_verification(self):
        assert ProductPageBrowserExtractor._is_shopee_login_required(
            "https://shopee.vn/verify/otp",
            "Shopee verification",
            "Quet ma QR hoac nhap ma OTP SMS de tiep tuc",
        )

    def test_merge_browser_candidates_prefers_dom_images(self):
        html_result = ProductPageExtractionResult(
            page_url="https://shop.example.com/products/team-jersey",
            best_candidate_url=None,
            candidates=[],
        )

        result = ProductPageBrowserExtractor._merge_browser_candidates(
            page_url="https://shop.example.com/products/team-jersey",
            html_result=html_result,
            dom_urls=["https://cdn.example.com/images/jersey-main.jpg"],
            max_candidates=5,
        )

        assert (
            result.best_candidate_url
            == "https://cdn.example.com/images/jersey-main.jpg"
        )
        assert result.candidates[0].source == "browser-dom"
