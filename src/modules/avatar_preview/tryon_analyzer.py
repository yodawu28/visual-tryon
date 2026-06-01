"""
Multimodal analyzer primitives for avatar try-on planning.
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.modules.avatar_preview.profile import (
    AvatarFraming,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
    avatar_framing_for_garment_region,
)

ANALYZER_PROMPT_VERSION = "avatar-tryon-analyzer-v1"


class TryOnIntent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    garment_region: GarmentRegion
    garment_type: GarmentType = GarmentType.UNKNOWN
    sleeve_length: GarmentSleeveLength = GarmentSleeveLength.UNKNOWN
    neckline: str = "unknown"
    dominant_colors: list[str] = Field(default_factory=list)
    logo_or_text: str = "unknown"
    pattern: str = "unknown"
    risk_notes: list[str] = Field(default_factory=list)
    recommended_avatar_framing: AvatarFraming | None = None

    @field_validator("garment_region", mode="before")
    @classmethod
    def normalize_garment_region(cls, value: Any) -> Any:
        return _normalize_choice(
            value,
            {
                "upper body": GarmentRegion.UPPER_BODY,
                "upper-body": GarmentRegion.UPPER_BODY,
                "top": GarmentRegion.UPPER_BODY,
                "tops": GarmentRegion.UPPER_BODY,
                "lower body": GarmentRegion.LOWER_BODY,
                "lower-body": GarmentRegion.LOWER_BODY,
                "bottom": GarmentRegion.LOWER_BODY,
                "bottoms": GarmentRegion.LOWER_BODY,
                "full body": GarmentRegion.FULL_BODY,
                "full-body": GarmentRegion.FULL_BODY,
                "one piece": GarmentRegion.FULL_BODY,
                "one-piece": GarmentRegion.FULL_BODY,
            },
        )

    @field_validator("garment_type", mode="before")
    @classmethod
    def normalize_garment_type(cls, value: Any) -> Any:
        return _normalize_choice(
            value,
            {
                "t-shirt": GarmentType.T_SHIRT,
                "tee": GarmentType.T_SHIRT,
                "tee shirt": GarmentType.T_SHIRT,
                "sports jersey": GarmentType.JERSEY,
                "jersey shirt": GarmentType.JERSEY,
                "trousers": GarmentType.PANTS,
                "jeans": GarmentType.PANTS,
                "short pants": GarmentType.SHORTS,
                "one-piece": GarmentType.DRESS,
                "one piece": GarmentType.DRESS,
                "matching set": GarmentType.SET,
                "outfit": GarmentType.FULL_OUTFIT,
            },
        )

    @field_validator("sleeve_length", mode="before")
    @classmethod
    def normalize_sleeve_length(cls, value: Any) -> Any:
        return _normalize_choice(
            value,
            {
                "short sleeve": GarmentSleeveLength.SHORT_SLEEVE,
                "short sleeves": GarmentSleeveLength.SHORT_SLEEVE,
                "short-sleeve": GarmentSleeveLength.SHORT_SLEEVE,
                "short-sleeved": GarmentSleeveLength.SHORT_SLEEVE,
                "long sleeve": GarmentSleeveLength.LONG_SLEEVE,
                "long sleeves": GarmentSleeveLength.LONG_SLEEVE,
                "long-sleeve": GarmentSleeveLength.LONG_SLEEVE,
                "long-sleeved": GarmentSleeveLength.LONG_SLEEVE,
                "no sleeves": GarmentSleeveLength.SLEEVELESS,
                "sleeve less": GarmentSleeveLength.SLEEVELESS,
                "tank": GarmentSleeveLength.SLEEVELESS,
            },
        )

    @field_validator("recommended_avatar_framing", mode="before")
    @classmethod
    def normalize_avatar_framing(cls, value: Any) -> Any:
        return _normalize_choice(
            value,
            {
                "upper body": AvatarFraming.UPPER_BODY,
                "upper-body": AvatarFraming.UPPER_BODY,
                "full body": AvatarFraming.FULL_BODY,
                "full-body": AvatarFraming.FULL_BODY,
            },
        )

    @field_validator("dominant_colors", "risk_notes", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value)]

    @field_validator("neckline", "logo_or_text", "pattern", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip()
        return normalized or "unknown"

    @model_validator(mode="after")
    def fill_derived_defaults(self) -> "TryOnIntent":
        if self.recommended_avatar_framing is None:
            self.recommended_avatar_framing = avatar_framing_for_garment_region(
                self.garment_region
            )
        return self


class OllamaTryOnAnalyzer:
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 300.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "provider": "ollama",
            "model": self.model,
            "analyzer_prompt_version": ANALYZER_PROMPT_VERSION,
        }

    def analyze_images(
        self, *, avatar_image: bytes, garment_image: bytes
    ) -> TryOnIntent:
        prompt = build_tryon_analyzer_prompt()
        images = [
            _prepare_ollama_image_base64(avatar_image),
            _prepare_ollama_image_base64(garment_image),
        ]
        response = self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": images,
                    }
                ],
                "stream": False,
                "format": "json",
            },
        )
        if response.status_code == 404:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": images,
                    "stream": False,
                    "format": "json",
                },
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                "Ollama analyzer request failed. Check OLLAMA_BASE_URL, "
                f"model '{self.model}', and whether the local Ollama server "
                f"supports /api/chat or /api/generate. Last URL: "
                f"{exc.request.url}"
            ) from exc
        return parse_tryon_intent_response(_response_content(response.json()))


def build_tryon_analyzer_prompt() -> str:
    return (
        "You are a virtual try-on planning analyzer. You receive IMAGE 1 as a "
        "synthetic avatar or anonymized user reference, and IMAGE 2 as the "
        "garment/product reference. Return JSON only. Do not generate an image. "
        "Do not include markdown.\n\n"
        "Analyze IMAGE 2 carefully and return exactly one JSON object with these "
        "keys:\n"
        "- garment_region: one of upper_body, lower_body, full_body\n"
        "- garment_type: one of shirt, t_shirt, jersey, jacket, hoodie, pants, "
        "shorts, skirt, dress, set, full_outfit, unknown\n"
        "- sleeve_length: one of sleeveless, short_sleeve, long_sleeve, unknown\n"
        "- neckline: short phrase such as crew neck, v-neck, collar, unknown\n"
        "- dominant_colors: list of visible garment colors\n"
        "- logo_or_text: describe visible logos, patches, numbers, or text; use "
        "unknown if none\n"
        "- pattern: describe stripes, panels, trims, texture, or fabric pattern; "
        "use unknown if plain\n"
        "- risk_notes: list of try-on risks, especially sleeve, arm, logo, text, "
        "or background contamination risks\n"
        "- recommended_avatar_framing: one of upper_body, full_body\n\n"
        "Do not choose or recommend a generation provider. The product pipeline "
        "always uses its configured Qwen avatar preview generator. Prefer "
        "full_body when the garment is lower_body or full_body, or when an "
        "upper-body garment must be shown with stable hips and legs."
    )


def build_multimodal_tryon_prompt(
    *,
    base_prompt: str,
    intent: TryOnIntent,
) -> str:
    return (
        f"{base_prompt.strip()} "
        "Multimodal garment analysis from the avatar and product images: "
        f"garment_region={intent.garment_region.value}; "
        f"garment_type={intent.garment_type.value}; "
        f"sleeve_length={intent.sleeve_length.value}; "
        f"neckline={intent.neckline}; "
        f"dominant_colors={', '.join(intent.dominant_colors) or 'unknown'}; "
        f"logo_or_text={intent.logo_or_text}; "
        f"pattern={intent.pattern}. "
        "Use this structured analysis as the source of truth for category, "
        "sleeve length, visible garment details, logos, text, colors, and "
        "pattern preservation. "
        f"Known try-on risks: {'; '.join(intent.risk_notes) or 'unknown'}."
    )


def parse_tryon_intent_response(response: str | dict[str, Any]) -> TryOnIntent:
    if isinstance(response, dict):
        return TryOnIntent.model_validate(response)
    if not isinstance(response, str):
        raise ValueError("Analyzer response must be a valid JSON object or string")

    parsed = _extract_json_object(response)
    if not isinstance(parsed, dict):
        raise ValueError("Analyzer response must include a valid JSON object")
    return TryOnIntent.model_validate(parsed)


def _extract_json_object(response: str) -> Any:
    stripped = response.strip()
    if not stripped:
        raise ValueError("Analyzer response must include a valid JSON object")

    if "```" in stripped:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Analyzer response must include a valid JSON object")
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Analyzer response must include a valid JSON object"
            ) from exc


def _response_content(response_payload: dict[str, Any]) -> str | dict[str, Any]:
    message = response_payload.get("message")
    if isinstance(message, dict) and "content" in message:
        return message["content"]

    choices = response_payload.get("choices")
    if isinstance(choices, list) and choices:
        choice_message = (
            choices[0].get("message") if isinstance(choices[0], dict) else None
        )
        if isinstance(choice_message, dict) and "content" in choice_message:
            return choice_message["content"]

    if "response" in response_payload:
        return response_payload["response"]

    raise ValueError("Analyzer response did not include message content")


def _prepare_ollama_image_base64(image_bytes: bytes) -> str:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = image.convert("RGB")
            image.thumbnail((768, 768), Image.Resampling.LANCZOS)

            canvas = Image.new("RGB", (768, 768), color=(255, 255, 255))
            offset = ((768 - image.width) // 2, (768 - image.height) // 2)
            canvas.paste(image, offset)

            output = io.BytesIO()
            canvas.save(output, format="JPEG", quality=88, optimize=True)
    except UnidentifiedImageError as exc:
        raise ValueError(
            "Unsupported image payload. Supported formats: png, jpeg, gif, webp"
        ) from exc

    return base64.b64encode(output.getvalue()).decode("utf-8")


def _normalize_choice(value: Any, aliases: dict[str, Any]) -> Any:
    if value is None:
        return value
    if not isinstance(value, str):
        return value

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    for alias, canonical in aliases.items():
        if normalized == alias.strip().lower().replace("-", "_").replace(" ", "_"):
            return canonical
    return normalized
