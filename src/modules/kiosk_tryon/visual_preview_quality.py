"""Visual-preview-specific capture quality checks."""

from __future__ import annotations

from typing import Any


def require_visual_preview_capture_ready(capture_analysis: dict[str, Any]) -> None:
    if capture_analysis.get("passed") is not True:
        raise ValueError("capture analysis must pass before visual preview")

    gate = _visual_preview_gate(capture_analysis)
    if gate is None:
        raise ValueError(
            "capture quality gate is missing; re-run capture analysis before "
            "visual preview"
        )
    if gate.get("visual_preview_ready") is True:
        return

    guidance = gate.get("guidance")
    guidance_text = ""
    if isinstance(guidance, list) and guidance:
        clean_guidance = [str(item) for item in guidance if str(item).strip()]
        if clean_guidance:
            guidance_text = f": {'; '.join(clean_guidance)}"
    raise ValueError(
        "capture quality is not ready for visual preview" f"{guidance_text}"
    )


def visual_preview_capture_ready(capture_analysis: dict[str, Any] | None) -> bool:
    if not isinstance(capture_analysis, dict):
        return False
    try:
        require_visual_preview_capture_ready(capture_analysis)
    except ValueError:
        return False
    return True


def _visual_preview_gate(capture_analysis: dict[str, Any]) -> dict[str, Any] | None:
    quality_gates = capture_analysis.get("quality_gates")
    if not isinstance(quality_gates, dict):
        return None
    gate = quality_gates.get("category_visual_preview")
    return gate if isinstance(gate, dict) else None
