"""
Semantic parser client cho image analysis.
"""

import base64
import io
import json
import logging
import re
import httpx
from openai import OpenAI
from PIL import Image, UnidentifiedImageError

from src.config.settings import get_settings
from src.schemas.responses import ClothingAnalysis
from src.modules.semantic_parser.prompt_builder import PromptBuilder, PromptStrategy

logger = logging.getLogger(__name__)


class SemanticParserClient:
    """
    Vision semantic parser client.

    Uses Ollama local VLM support by default, with OpenAI available as an
    explicit provider for fallback or evaluation.
    """

    def __init__(self):
        settings = get_settings()
        self.provider = settings.semantic_parser_provider.lower()
        self.client = None
        self.ollama_client = None

        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when SEMANTIC_PARSER_PROVIDER=openai"
                )
            self.client = OpenAI(
                api_key=settings.openai_api_key, timeout=settings.openai_timeout
            )
            self.model = settings.openai_model
        elif self.provider == "ollama":
            self.ollama_base_url = settings.ollama_base_url.rstrip("/")
            self.model = settings.ollama_model
            self.ollama_client = httpx.Client(timeout=settings.ollama_timeout)
        else:
            raise ValueError(
                "Invalid SEMANTIC_PARSER_PROVIDER: "
                f"{self.provider}. Must be 'openai' or 'ollama'"
            )

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "semantic_prompt_version": PromptBuilder.get_prompt_version(
                PromptStrategy.EDIT_SAFE
            ),
        }

    def analyze_vto_context(
        self, user_image_b64: str, product_image_b64: str
    ) -> ClothingAnalysis:
        """
        Analyze cả user photo và product image.

        Args:
            user_image_b64: Base64 encoded anonymized user image
            product_image_b64: Base64 encoded Shopee product image

        Returns:
            ClothingAnalysis với detailed descriptions
        """

        if self.provider == "ollama":
            return self._analyze_vto_context_ollama(user_image_b64, product_image_b64)

        return self._analyze_vto_context_openai(user_image_b64, product_image_b64)

    def _analyze_vto_context_openai(
        self, user_image_b64: str, product_image_b64: str
    ) -> ClothingAnalysis:
        # Build prompt
        prompt = self._build_analysis_prompt()
        user_image_data_url = self._prepare_openai_image_data_url(user_image_b64)
        product_image_data_url = self._prepare_openai_image_data_url(product_image_b64)

        logger.info("Calling OpenAI GPT-4o Vision API for VTO analysis...")

        # Call GPT-4o Vision với structured output
        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert fashion AI assistant specialized in virtual try-on analysis.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": user_image_data_url,
                                    "detail": "high",
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": product_image_data_url,
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                response_format=ClothingAnalysis,
                temperature=0.3,  # Lower temperature for consistency
            )

            message = completion.choices[0].message

            if message.parsed:
                logger.info("Successfully parsed VTO analysis from OpenAI")
                return message.parsed
            else:
                logger.error(f"OpenAI refused to parse: {message.refusal}")
                raise ValueError(f"OpenAI refused to parse: {message.refusal}")

        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise

    def _build_analysis_prompt(self) -> str:
        """
        Build engineered prompt cho VTO analysis.
        """
        return PromptBuilder.build_vto_prompt(strategy=PromptStrategy.EDIT_SAFE)

    def _analyze_vto_context_ollama(
        self, user_image_b64: str, product_image_b64: str
    ) -> ClothingAnalysis:
        prompt = (
            f"{self._build_analysis_prompt()}\n\n"
            "Return JSON only with exactly these keys: clothing_description, "
            "body_pose, inpainting_prompt, confidence_score, additional_notes."
        )
        user_image_b64 = self._prepare_ollama_image_base64(user_image_b64)
        product_image_b64 = self._prepare_ollama_image_base64(product_image_b64)

        logger.info("Calling Ollama VLM API for VTO analysis (model=%s)...", self.model)

        try:
            response = self.ollama_client.post(
                f"{self.ollama_base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [user_image_b64, product_image_b64],
                        }
                    ],
                    "stream": False,
                    "format": "json",
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Ollama VTO analysis failed with status %s: %s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise
            analysis = self._parse_ollama_analysis_response(response.json())
            analysis.inpainting_prompt = (
                PromptBuilder.build_edit_safe_inpainting_prompt(
                    clothing_description=analysis.clothing_description,
                    body_pose=analysis.body_pose,
                )
            )
            logger.info("Successfully parsed VTO analysis from Ollama")
            return analysis
        except Exception as e:
            logger.error(f"Ollama VTO analysis call failed: {str(e)}")
            raise

    @classmethod
    def _prepare_ollama_image_base64(cls, image_b64: str) -> str:
        normalized = cls._normalize_base64_image(image_b64)
        decoded = base64.b64decode(normalized)

        try:
            with Image.open(io.BytesIO(decoded)) as image:
                image = image.convert("RGB")
                image.thumbnail((512, 512), Image.Resampling.LANCZOS)

                canvas = Image.new("RGB", (512, 512), color=(255, 255, 255))
                offset = (
                    (512 - image.width) // 2,
                    (512 - image.height) // 2,
                )
                canvas.paste(image, offset)

                output = io.BytesIO()
                canvas.save(output, format="JPEG", quality=85, optimize=True)
        except UnidentifiedImageError as exc:
            raise ValueError(
                "Unsupported image payload. Supported formats: png, jpeg, gif, webp"
            ) from exc

        return base64.b64encode(output.getvalue()).decode("utf-8")

    @staticmethod
    def _parse_ollama_analysis_response(response_payload: dict) -> ClothingAnalysis:
        content = None

        message = response_payload.get("message")
        if isinstance(message, dict):
            content = message.get("content")

        if content is None and response_payload.get("choices"):
            choice = response_payload["choices"][0]
            if isinstance(choice, dict):
                message = choice.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")

        if isinstance(content, dict):
            data = content
        elif isinstance(content, str):
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError("Ollama returned invalid JSON analysis") from exc
        else:
            raise ValueError("Ollama response did not include analysis content")

        if not data.get("inpainting_prompt"):
            data["inpainting_prompt"] = PromptBuilder.build_edit_safe_inpainting_prompt(
                clothing_description=data.get("clothing_description", ""),
                body_pose=data.get("body_pose", ""),
            )

        return ClothingAnalysis(**data)

    @staticmethod
    def _normalize_base64_image(image_b64: str) -> str:
        """
        Normalize user/product image payloads into canonical base64 before sending
        them as data URLs to OpenAI.
        """
        if not image_b64:
            raise ValueError("Image payload is empty")

        normalized = image_b64.strip()

        if normalized.startswith("data:"):
            try:
                normalized = normalized.split("base64,", 1)[1]
            except IndexError as exc:
                raise ValueError("Invalid data URL image payload") from exc

        normalized = re.sub(r"\s+", "", normalized)
        normalized = normalized.replace("-", "+").replace("_", "/")

        missing_padding = len(normalized) % 4
        if missing_padding:
            normalized += "=" * (4 - missing_padding)

        try:
            decoded = base64.b64decode(normalized, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 image payload") from exc

        return base64.b64encode(decoded).decode("utf-8")

    @classmethod
    def _prepare_openai_image_data_url(cls, image_b64: str) -> str:
        normalized = cls._normalize_base64_image(image_b64)
        decoded = base64.b64decode(normalized)

        try:
            with Image.open(io.BytesIO(decoded)) as image:
                image.load()
                image_format = (image.format or "").lower()
        except UnidentifiedImageError as exc:
            raise ValueError(
                "Unsupported image payload. Supported formats: png, jpeg, gif, webp"
            ) from exc

        if image_format == "jpg":
            image_format = "jpeg"

        if image_format not in {"png", "jpeg", "gif", "webp"}:
            raise ValueError(
                "Unsupported image payload. Supported formats: png, jpeg, gif, webp"
            )

        return f"data:image/{image_format};base64,{normalized}"
