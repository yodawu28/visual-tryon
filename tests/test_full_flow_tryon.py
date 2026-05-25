from unittest.mock import AsyncMock, patch
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.generation import manual_router
from src.modules.product_ingestion.image_fetcher import ProductImageResult
from src.schemas.responses import ClothingAnalysis
from tests.test_semantic_parser import _build_base64_image


class TestFullFlowTryOnRoute:
    def setup_method(self):
        app = FastAPI()
        app.include_router(manual_router)
        self.client = TestClient(app)

    def test_full_flow_uses_product_image_directly(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.92,
            additional_notes="",
        )

        with patch(
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(anonymized_user_image, 1, [(8, 8, 24, 24)])),
        ) as anonymize_mock, patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ) as analyze_mock, patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={
                    "product_image": _build_base64_image("JPEG"),
                    "privacy_level": "extreme",
                    "size": "1024x1024",
                },
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["faces_detected"] == 1
        assert payload["anonymized_image"] == anonymized_user_image
        assert payload["privacy_level_used"] == "standard"
        assert payload["warnings"] == [
            "privacy_level 'extreme' was overridden to 'standard' because Replicate preview currently supports standard only."
        ]
        assert payload["product_source_mode"] == "product_image"
        assert payload["product_source_url"] is None
        assert payload["generated_image"] is not None
        assert payload["mask_supported"] is True
        assert payload["mask_applied"] is False
        assert payload["face_preserve_applied"] is True
        assert payload["face_preserve_source"] == "full-flow original face bbox"
        anonymize_mock.assert_called_once()
        analyze_mock.assert_called_once_with(
            user_image_b64=anonymized_user_image,
            product_image_b64=_build_base64_image("JPEG"),
        )

    def test_full_flow_fetches_image_url_when_needed(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.92,
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
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(anonymized_user_image, 2, [(8, 8, 24, 24)])),
        ), patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.manual_product_image_fetcher.fetch_image_from_url",
            new=AsyncMock(return_value=fetched_image),
        ) as fetch_mock, patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={
                    "image_url": "https://cdn.example.com/jersey.jpg",
                    "privacy_level": "strong",
                    "size": "1024x1024",
                },
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["faces_detected"] == 2
        assert payload["privacy_level_used"] == "standard"
        assert payload["warnings"] == [
            "privacy_level 'strong' was overridden to 'standard' because Replicate preview currently supports standard only."
        ]
        assert payload["product_source_mode"] == "image_url"
        assert payload["product_source_url"] == "https://cdn.example.com/jersey.jpg"
        assert payload["mask_supported"] is True
        assert payload["mask_applied"] is False
        assert payload["face_preserve_applied"] is True
        assert payload["face_preserve_source"] == "full-flow original face bbox"
        fetch_mock.assert_called_once_with("https://cdn.example.com/jersey.jpg")

    def test_full_flow_ignores_placeholder_product_image_and_uses_image_url(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.92,
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
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(anonymized_user_image, 1, [(8, 8, 24, 24)])),
        ), patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.manual_product_image_fetcher.fetch_image_from_url",
            new=AsyncMock(return_value=fetched_image),
        ) as fetch_mock, patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ) as analyze_mock, patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={
                    "product_image": "undefined",
                    "image_url": "https://cdn.example.com/jersey.jpg",
                    "privacy_level": "extreme",
                    "size": "1024x1024",
                },
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["product_source_mode"] == "image_url"
        assert payload["product_source_url"] == "https://cdn.example.com/jersey.jpg"
        assert payload["warnings"] == [
            "privacy_level 'extreme' was overridden to 'standard' because Replicate preview currently supports standard only."
        ]
        fetch_mock.assert_called_once_with("https://cdn.example.com/jersey.jpg")
        analyze_mock.assert_called_once_with(
            user_image_b64=anonymized_user_image,
            product_image_b64="fetched_product_base64",
        )

    def test_full_flow_falls_back_to_image_url_when_product_image_is_invalid(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.92,
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
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(anonymized_user_image, 1, [(8, 8, 24, 24)])),
        ), patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.manual_product_image_fetcher.fetch_image_from_url",
            new=AsyncMock(return_value=fetched_image),
        ) as fetch_mock, patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ) as analyze_mock, patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={
                    "product_image": "definitely-not-an-image",
                    "image_url": "https://cdn.example.com/jersey.jpg",
                    "privacy_level": "extreme",
                    "size": "1024x1024",
                },
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["product_source_mode"] == "image_url"
        assert payload["product_source_url"] == "https://cdn.example.com/jersey.jpg"
        assert payload["warnings"] == [
            "privacy_level 'extreme' was overridden to 'standard' because Replicate preview currently supports standard only."
        ]
        fetch_mock.assert_called_once_with("https://cdn.example.com/jersey.jpg")
        analyze_mock.assert_called_once_with(
            user_image_b64=anonymized_user_image,
            product_image_b64="fetched_product_base64",
        )

    def test_full_flow_returns_no_warning_when_standard_privacy_is_requested(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        anonymized_user_image = _build_base64_image("JPEG")
        generated_image = _build_base64_image("PNG")
        analysis = ClothingAnalysis(
            clothing_description="Blue jersey",
            body_pose="Standing straight",
            inpainting_prompt="Edit image 1 only and swap upper body clothing.",
            confidence_score=0.92,
            additional_notes="",
        )

        with patch(
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(anonymized_user_image, 1, [(8, 8, 24, 24)])),
        ), patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ), patch(
            "src.api.routes.generation.manual_product_semantic_parser.analyze_vto_context",
            return_value=analysis,
        ), patch(
            "src.api.routes.generation.image_generator.generate_tryon_from_b64",
            return_value=generated_image,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={
                    "product_image": _build_base64_image("JPEG"),
                    "privacy_level": "standard",
                    "size": "1024x1024",
                },
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["privacy_level_used"] == "standard"
        assert payload["warnings"] == []

    def test_full_flow_rejects_invalid_product_image_without_image_url(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        with patch(
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(_build_base64_image("JPEG"), 1, [])),
        ), patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={
                    "product_image": "definitely-not-an-image",
                    "privacy_level": "extreme",
                    "size": "1024x1024",
                },
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 422
        assert (
            "product_image must be a supported base64 image"
            in response.json()["detail"]
        )

    def test_full_flow_requires_product_source(self):
        settings = Mock()
        settings.image_gen_mode = "qwen-fast"
        with patch(
            "src.api.routes.generation._anonymize_uploaded_user_image",
            new=AsyncMock(return_value=(_build_base64_image("JPEG"), 1, [])),
        ), patch(
            "src.api.routes.generation.get_settings",
            return_value=settings,
        ):
            response = self.client.post(
                "/api/v1/tryon/full-flow",
                data={"privacy_level": "extreme"},
                files={"user_file": ("user.jpg", b"fake-user-image", "image/jpeg")},
            )

        assert response.status_code == 422
        assert "product_image or image_url" in response.json()["detail"]
