from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.generation import manual_router
from src.modules.product_ingestion.image_fetcher import ProductImageResult
from src.schemas.responses import ClothingAnalysis
from tests.test_semantic_parser import _build_base64_image


class TestManualProductTryOnRoute:
    def setup_method(self):
        app = FastAPI()
        app.include_router(manual_router)
        self.client = TestClient(app)

    def test_manual_product_tryon_uses_product_image_directly(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue sports jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.95,
            additional_notes="",
        )

        with patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ) as analyze_mock, patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ) as generate_mock:
            response = self.client.post(
                "/api/v1/tryon/manual-product",
                json={
                    "anonymized_user_image": anonymized_user_image,
                    "product_image": _build_base64_image("JPEG"),
                    "size": "1024x1024",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["product_source_mode"] == "product_image"
        assert payload["product_source_url"] is None
        assert payload["generated_image"] is not None
        assert payload["mask_supported"] is True
        assert payload["mask_applied"] is False
        assert payload["analysis"]["inpainting_prompt"] == analysis.inpainting_prompt
        analyze_mock.assert_called_once_with(
            user_image_b64=anonymized_user_image,
            product_image_b64=_build_base64_image("JPEG"),
        )
        generate_mock.assert_called_once()

    def test_manual_product_tryon_fetches_image_url_when_product_image_missing(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue sports jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.95,
            additional_notes="",
        )
        fetched_image = ProductImageResult(
            source_url="https://cdn.example.com/jersey.jpg",
            content_type="image/jpeg",
            image_base64="fetched_product_base64",
            normalized_format="jpeg",
            size_bytes=1234,
        )

        with patch(
            "src.api.routes.generation.manual_product_image_fetcher.fetch_image_from_url",
            new=AsyncMock(return_value=fetched_image),
        ) as fetch_mock, patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ) as analyze_mock, patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ):
            response = self.client.post(
                "/api/v1/tryon/manual-product",
                json={
                    "anonymized_user_image": anonymized_user_image,
                    "image_url": "https://cdn.example.com/jersey.jpg",
                    "size": "1024x1024",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["product_source_mode"] == "image_url"
        assert payload["product_source_url"] == "https://cdn.example.com/jersey.jpg"
        assert payload["mask_supported"] is True
        assert payload["mask_applied"] is False
        fetch_mock.assert_called_once_with("https://cdn.example.com/jersey.jpg")
        analyze_mock.assert_called_once_with(
            user_image_b64=anonymized_user_image,
            product_image_b64="fetched_product_base64",
        )

    def test_manual_product_tryon_requires_product_source(self):
        response = self.client.post(
            "/api/v1/tryon/manual-product",
            json={
                "anonymized_user_image": "user_base64",
                "size": "1024x1024",
            },
        )

        assert response.status_code == 422
        assert "product_image or image_url" in response.json()["detail"]
