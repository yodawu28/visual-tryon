import io
import json as json_lib

import httpx
import pytest
from PIL import Image

from src.modules.avatar_preview.profile import (
    AvatarFraming,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)
from src.modules.avatar_preview.tryon_analyzer import (
    ANALYZER_PROMPT_VERSION,
    OllamaTryOnAnalyzer,
    build_tryon_analyzer_prompt,
    parse_tryon_intent_response,
)


def test_parse_tryon_intent_response_normalizes_common_model_aliases():
    raw_response = """
    Here is the result:
    ```json
    {
      "garment_region": "upper body",
      "garment_type": "t-shirt",
      "sleeve_length": "short sleeve",
      "neckline": "v-neck",
      "dominant_colors": ["mint green", "navy blue"],
      "logo_or_text": "Yonex mark and Korea flag patch",
      "pattern": "subtle geometric tonal pattern",
      "risk_notes": ["short sleeve can be confused with long sleeve base layer"],
      "recommended_avatar_framing": "full body"
    }
    ```
    """

    intent = parse_tryon_intent_response(raw_response)

    assert intent.garment_region == GarmentRegion.UPPER_BODY
    assert intent.garment_type == GarmentType.T_SHIRT
    assert intent.sleeve_length == GarmentSleeveLength.SHORT_SLEEVE
    assert intent.recommended_avatar_framing == AvatarFraming.FULL_BODY
    assert intent.dominant_colors == ["mint green", "navy blue"]
    assert "Yonex" in intent.logo_or_text
    assert "short sleeve" in intent.risk_notes[0]


def test_parse_tryon_intent_response_fills_safe_defaults():
    intent = parse_tryon_intent_response(
        {
            "garment_region": "lower_body",
            "garment_type": "shorts",
            "sleeve_length": "unknown",
        }
    )

    assert intent.garment_region == GarmentRegion.LOWER_BODY
    assert intent.garment_type == GarmentType.SHORTS
    assert intent.sleeve_length == GarmentSleeveLength.UNKNOWN
    assert intent.recommended_avatar_framing == AvatarFraming.FULL_BODY
    assert intent.logo_or_text == "unknown"
    assert intent.pattern == "unknown"


def test_parse_tryon_intent_response_rejects_missing_json():
    with pytest.raises(ValueError, match="valid JSON object"):
        parse_tryon_intent_response("The garment is a mint jersey.")


def test_build_tryon_analyzer_prompt_defines_stable_json_contract():
    prompt = build_tryon_analyzer_prompt()

    assert ANALYZER_PROMPT_VERSION == "avatar-tryon-analyzer-v1"
    assert "Return JSON only" in prompt
    assert "garment_region" in prompt
    assert "sleeve_length" in prompt
    assert "short_sleeve" in prompt
    assert "Do not choose or recommend a generation provider" in prompt
    assert "Qwen avatar preview generator" in prompt


def test_ollama_tryon_analyzer_falls_back_to_generate_when_chat_is_missing(
    monkeypatch,
):
    calls: list[tuple[str, dict]] = []
    response_payload = {
        "garment_region": "upper_body",
        "garment_type": "jersey",
        "sleeve_length": "short_sleeve",
    }

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        def post(self, url, json):
            calls.append((url, json))
            request = httpx.Request("POST", url)
            if url.endswith("/api/chat"):
                return httpx.Response(
                    404,
                    json={"error": "not found"},
                    request=request,
                )
            return httpx.Response(
                200,
                json={"response": json_lib.dumps(response_payload)},
                request=request,
            )

    monkeypatch.setattr(
        "src.modules.avatar_preview.tryon_analyzer.httpx.Client",
        FakeClient,
    )

    analyzer = OllamaTryOnAnalyzer(
        model="qwen2.5vl:7b",
        base_url="http://127.0.0.1:11434",
    )

    intent = analyzer.analyze_images(
        avatar_image=_png_bytes(),
        garment_image=_png_bytes(),
    )

    assert [url for url, _payload in calls] == [
        "http://127.0.0.1:11434/api/chat",
        "http://127.0.0.1:11434/api/generate",
    ]
    assert calls[1][1]["prompt"] == build_tryon_analyzer_prompt()
    assert len(calls[1][1]["images"]) == 2
    assert intent.garment_region == GarmentRegion.UPPER_BODY
    assert intent.garment_type == GarmentType.JERSEY
    assert intent.sleeve_length == GarmentSleeveLength.SHORT_SLEEVE


def test_ollama_tryon_analyzer_wraps_http_errors_with_helpful_message(monkeypatch):
    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        def post(self, url, json):
            return httpx.Response(
                404,
                json={"error": "not found"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "src.modules.avatar_preview.tryon_analyzer.httpx.Client",
        FakeClient,
    )

    analyzer = OllamaTryOnAnalyzer(
        model="qwen2.5vl:7b",
        base_url="http://127.0.0.1:11434",
    )

    with pytest.raises(ValueError, match="Ollama analyzer request failed"):
        analyzer.analyze_images(
            avatar_image=_png_bytes(),
            garment_image=_png_bytes(),
        )


def _png_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), color=(245, 245, 245))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
