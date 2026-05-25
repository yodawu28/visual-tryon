"""
Tests cho Semantic Parser module.
"""

import base64
import io
import json
import pytest
from unittest.mock import Mock, patch
from PIL import Image

from src.modules.semantic_parser.openai_client import SemanticParserClient
from src.modules.semantic_parser.prompt_builder import PromptBuilder, PromptStrategy
from src.schemas.responses import ClothingAnalysis


@pytest.fixture
def mock_settings():
    """Mock settings"""
    with patch("src.modules.semantic_parser.openai_client.get_settings") as mock:
        settings = Mock()
        settings.openai_api_key = "sk-test-key"
        settings.openai_model = "gpt-4o"
        settings.openai_timeout = 30
        settings.semantic_parser_provider = "openai"
        settings.ollama_base_url = "http://127.0.0.1:11434"
        settings.ollama_model = "vto-brain"
        settings.ollama_timeout = 300
        mock.return_value = settings
        yield settings


@pytest.fixture
def semantic_parser_client(mock_settings):
    """Create SemanticParserClient with mocked settings"""
    with patch("src.modules.semantic_parser.openai_client.OpenAI"):
        return SemanticParserClient()


def _build_base64_image(image_format: str = "JPEG") -> str:
    image = Image.new("RGB", (32, 32), color=(12, 34, 56))
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _build_base64_image_with_size(
    width: int,
    height: int,
    image_format: str = "JPEG",
) -> str:
    image = Image.new("RGB", (width, height), color=(12, 34, 56))
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class TestSemanticParserClient:
    def test_initialization(self, mock_settings):
        """Test client initialization"""
        with patch("src.modules.semantic_parser.openai_client.OpenAI") as mock_openai:
            client = SemanticParserClient()

            mock_openai.assert_called_once_with(api_key="sk-test-key", timeout=30)
            assert client.model == "gpt-4o"

    def test_metadata_for_openai_provider(self, semantic_parser_client):
        metadata = semantic_parser_client.get_runtime_metadata()

        assert metadata == {
            "provider": "openai",
            "model": "gpt-4o",
            "semantic_prompt_version": "semantic-edit-safe-v1",
        }

    def test_metadata_for_ollama_provider(self, mock_settings):
        mock_settings.semantic_parser_provider = "ollama"

        with patch("httpx.Client"), patch(
            "src.modules.semantic_parser.openai_client.OpenAI"
        ) as mock_openai:
            client = SemanticParserClient()

        metadata = client.get_runtime_metadata()

        assert metadata == {
            "provider": "ollama",
            "model": "vto-brain",
            "semantic_prompt_version": "semantic-edit-safe-v1",
        }
        mock_openai.assert_not_called()

    def test_build_analysis_prompt(self, semantic_parser_client):
        """Test prompt building"""
        prompt = semantic_parser_client._build_analysis_prompt()

        assert isinstance(prompt, str)
        assert "IMAGE 1" in prompt
        assert "IMAGE 2" in prompt
        assert "clothing_description" in prompt
        assert "body_pose" in prompt
        assert "inpainting_prompt" in prompt
        assert "treats IMAGE 1 as the base photo" in prompt
        assert "uses IMAGE 2 only as the garment reference" in prompt
        assert "avoids text-to-image phrasing" in prompt

    def test_analyze_vto_context_success(self, semantic_parser_client):
        """Test successful VTO context analysis"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_message = Mock()
        mock_message.parsed = ClothingAnalysis(
            clothing_description="A blue cotton t-shirt",
            body_pose="Standing straight with arms at sides",
            inpainting_prompt="A blue cotton t-shirt on a person standing straight",
            confidence_score=0.95,
        )
        mock_response.choices = [Mock(message=mock_message)]

        semantic_parser_client.client.beta.chat.completions.parse = Mock(
            return_value=mock_response
        )

        # Test
        result = semantic_parser_client.analyze_vto_context(
            user_image_b64=_build_base64_image("JPEG"),
            product_image_b64=_build_base64_image("PNG"),
        )

        assert isinstance(result, ClothingAnalysis)
        assert result.clothing_description == "A blue cotton t-shirt"
        assert result.confidence_score == 0.95

    def test_analyze_vto_context_ollama_success(self, mock_settings):
        """Test successful VTO context analysis through Ollama provider."""
        mock_settings.semantic_parser_provider = "ollama"

        ollama_payload = {
            "clothing_description": "Light pink T-shirt with round neckline",
            "body_pose": "Arms crossed in front of chest",
            "inpainting_prompt": (
                "Use IMAGE 1 as the base photo and IMAGE 2 only as garment "
                "reference. Replace only the upper body clothing while preserving "
                "the anonymized face area, pose, framing, background, and lighting."
            ),
            "confidence_score": 0.93,
            "additional_notes": "No outliers detected.",
        }
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "message": {"content": json.dumps(ollama_payload)}
        }

        mock_http_client = Mock()
        mock_http_client.post.return_value = mock_response

        with patch(
            "src.modules.semantic_parser.openai_client.OpenAI"
        ) as mock_openai, patch("httpx.Client", return_value=mock_http_client):
            client = SemanticParserClient()
            result = client.analyze_vto_context(
                user_image_b64=_build_base64_image("JPEG"),
                product_image_b64=_build_base64_image("PNG"),
            )

        assert isinstance(result, ClothingAnalysis)
        assert result.clothing_description == ollama_payload["clothing_description"]
        assert result.body_pose == ollama_payload["body_pose"]
        assert result.inpainting_prompt != ollama_payload["inpainting_prompt"]
        assert "Use IMAGE 1 as the base photo" in result.inpainting_prompt
        assert "Use IMAGE 2 only as the garment reference" in result.inpainting_prompt
        assert "anonymized face area" in result.inpainting_prompt
        assert "body shape" in result.inpainting_prompt
        assert "hands and arms" in result.inpainting_prompt
        assert "background" in result.inpainting_prompt
        assert "lighting" in result.inpainting_prompt
        assert ollama_payload["clothing_description"] in result.inpainting_prompt
        assert result.confidence_score == 0.93
        mock_openai.assert_not_called()

        mock_http_client.post.assert_called_once()
        post_url = mock_http_client.post.call_args.args[0]
        post_payload = mock_http_client.post.call_args.kwargs["json"]

        assert post_url == "http://127.0.0.1:11434/api/chat"
        assert post_payload["model"] == "vto-brain"
        assert post_payload["stream"] is False
        assert post_payload["format"] == "json"
        message = post_payload["messages"][0]
        assert message["role"] == "user"
        assert isinstance(message["content"], str)
        assert "Return JSON only" in message["content"]
        assert len(message["images"]) == 2
        assert not message["images"][0].startswith("data:image/")
        assert not message["images"][1].startswith("data:image/")
        assert base64.b64decode(message["images"][0], validate=True)
        assert base64.b64decode(message["images"][1], validate=True)

    def test_analyze_vto_context_ollama_composes_prompt_when_model_omits_it(
        self, mock_settings
    ):
        """Ollama may omit inpainting_prompt because backend owns the template."""
        mock_settings.semantic_parser_provider = "ollama"

        ollama_payload = {
            "clothing_description": "Light green sports jersey with navy side panels",
            "body_pose": "Arms crossed over chest, standing upright",
            "confidence_score": 0.95,
            "additional_notes": "Flag patch visible on chest.",
        }
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "message": {"content": json.dumps(ollama_payload)}
        }

        mock_http_client = Mock()
        mock_http_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_http_client), patch(
            "src.modules.semantic_parser.openai_client.OpenAI"
        ):
            client = SemanticParserClient()
            result = client.analyze_vto_context(
                user_image_b64=_build_base64_image("JPEG"),
                product_image_b64=_build_base64_image("PNG"),
            )

        assert result.clothing_description == ollama_payload["clothing_description"]
        assert result.body_pose == ollama_payload["body_pose"]
        assert result.inpainting_prompt
        assert "Use IMAGE 1 as the base photo" in result.inpainting_prompt
        assert ollama_payload["clothing_description"] in result.inpainting_prompt

    def test_analyze_vto_context_ollama_resizes_images_before_request(
        self, mock_settings
    ):
        """Ollama provider should send bounded 512x512 JPEG payloads."""
        mock_settings.semantic_parser_provider = "ollama"

        ollama_payload = {
            "clothing_description": "Black jacket",
            "body_pose": "Standing front-facing",
            "inpainting_prompt": "Use IMAGE 1 as base and IMAGE 2 as garment reference.",
            "confidence_score": 0.9,
            "additional_notes": "",
        }
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "message": {"content": json.dumps(ollama_payload)}
        }

        mock_http_client = Mock()
        mock_http_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_http_client), patch(
            "src.modules.semantic_parser.openai_client.OpenAI"
        ):
            client = SemanticParserClient()
            client.analyze_vto_context(
                user_image_b64=_build_base64_image_with_size(1200, 800, "JPEG"),
                product_image_b64=_build_base64_image_with_size(640, 900, "PNG"),
            )

        post_payload = mock_http_client.post.call_args.kwargs["json"]
        images = post_payload["messages"][0]["images"]

        assert len(images) == 2
        for image_b64 in images:
            decoded = base64.b64decode(image_b64, validate=True)
            with Image.open(io.BytesIO(decoded)) as image:
                image.load()
                assert image.size == (512, 512)
                assert image.format == "JPEG"

    def test_analyze_vto_context_refusal(self, semantic_parser_client):
        """Test when OpenAI refuses to parse"""
        # Mock OpenAI refusal
        mock_response = Mock()
        mock_message = Mock()
        mock_message.parsed = None
        mock_message.refusal = "Content policy violation"
        mock_response.choices = [Mock(message=mock_message)]

        semantic_parser_client.client.beta.chat.completions.parse = Mock(
            return_value=mock_response
        )

        # Test
        with pytest.raises(ValueError, match="OpenAI refused to parse"):
            semantic_parser_client.analyze_vto_context(
                user_image_b64=_build_base64_image("JPEG"),
                product_image_b64=_build_base64_image("PNG"),
            )

    def test_normalize_base64_image_accepts_data_url_and_whitespace(
        self, semantic_parser_client
    ):
        raw = base64.b64encode(b"fake-image-bytes").decode("utf-8")
        data_url = f"data:image/jpeg;base64,\n{raw[:8]} \n{raw[8:]}"

        normalized = semantic_parser_client._normalize_base64_image(data_url)

        assert normalized == raw

    def test_normalize_base64_image_adds_padding(self, semantic_parser_client):
        raw = base64.b64encode(b"fake-image-bytes").decode("utf-8")
        unpadded = raw.rstrip("=")

        normalized = semantic_parser_client._normalize_base64_image(unpadded)

        assert normalized == raw

    def test_normalize_base64_image_rejects_invalid_payload(
        self, semantic_parser_client
    ):
        with pytest.raises(ValueError, match="Invalid base64 image payload"):
            semantic_parser_client._normalize_base64_image("not-valid-base64***")

    def test_prepare_openai_image_data_url_detects_actual_mime(
        self, semantic_parser_client
    ):
        data_url = semantic_parser_client._prepare_openai_image_data_url(
            _build_base64_image("PNG")
        )

        assert data_url.startswith("data:image/png;base64,")

    def test_prepare_openai_image_data_url_rejects_non_image_payload(
        self, semantic_parser_client
    ):
        non_image = base64.b64encode(b"not-an-image").decode("utf-8")

        with pytest.raises(
            ValueError,
            match="Unsupported image payload. Supported formats: png, jpeg, gif, webp",
        ):
            semantic_parser_client._prepare_openai_image_data_url(non_image)


class TestPromptBuilder:
    def test_build_vto_prompt_balanced(self):
        """Test balanced strategy prompt"""
        prompt = PromptBuilder.build_vto_prompt(strategy=PromptStrategy.BALANCED)

        assert isinstance(prompt, str)
        assert "IMAGE 1" in prompt
        assert "IMAGE 2" in prompt
        assert len(prompt) > 100

    def test_build_vto_prompt_detailed(self):
        """Test detailed strategy prompt"""
        prompt = PromptBuilder.build_vto_prompt(strategy=PromptStrategy.DETAILED)

        assert len(prompt) > 300  # Detailed should be longer
        assert "Material analysis" in prompt
        assert "Construction" in prompt

    def test_build_vto_prompt_fast(self):
        """Test fast strategy prompt"""
        prompt = PromptBuilder.build_vto_prompt(strategy=PromptStrategy.FAST)

        # Fast should be shorter
        balanced_prompt = PromptBuilder.build_vto_prompt(
            strategy=PromptStrategy.BALANCED
        )
        assert len(prompt) < len(balanced_prompt)

    def test_build_vto_prompt_edit_safe(self):
        """Test edit-safe strategy prompt"""
        prompt = PromptBuilder.build_vto_prompt(strategy=PromptStrategy.EDIT_SAFE)

        assert "treats IMAGE 1 as the base photo" in prompt
        assert "uses IMAGE 2 only as the garment reference" in prompt
        assert "avoids text-to-image phrasing" in prompt


@pytest.mark.parametrize(
    ("strategy", "expected_version"),
    [
        (PromptStrategy.DETAILED, "semantic-detailed-v1"),
        (PromptStrategy.BALANCED, "semantic-balanced-v1"),
        (PromptStrategy.FAST, "semantic-fast-v1"),
        (PromptStrategy.EDIT_SAFE, "semantic-edit-safe-v1"),
    ],
)
def test_prompt_builder_exposes_prompt_strategy_versions(strategy, expected_version):
    assert PromptBuilder.get_prompt_version(strategy) == expected_version


def test_prompt_builder_exposes_edit_safe_version():
    assert (
        PromptBuilder.get_prompt_version(PromptStrategy.EDIT_SAFE)
        == "semantic-edit-safe-v1"
    )


def test_prompt_builder_rejects_unknown_strategy_version():
    with pytest.raises(ValueError, match="Unsupported prompt strategy"):
        PromptBuilder.get_prompt_version("unknown-strategy")
