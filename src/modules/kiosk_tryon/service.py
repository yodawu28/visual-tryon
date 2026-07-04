"""
Persistent session state for the kiosk try-on flow.

The kiosk flow is intentionally staged:
1. optionally preview a garment on a synthetic avatar;
2. create a kiosk session from either that approved preview or direct garment selection;
3. capture user photos for the later personalized try-on step.
"""

from __future__ import annotations

import json
import inspect
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class KioskTryOnSession:
    session_id: str
    status: str
    garment_id: str | None
    avatar_cache_key: str | None = None
    avatar_preview_cache_key: str | None = None
    capture_keys: list[str] = field(default_factory=list)
    captures: dict[str, dict[str, Any]] = field(default_factory=dict)
    capture_analysis: dict[str, Any] | None = None
    personalized_tryon_key: str | None = None
    fit_analysis_key: str | None = None
    created_at: str = ""
    updated_at: str = ""


class KioskTryOnService:
    """
    File-backed session registry for local kiosk deployments.

    This deliberately stores only references plus kiosk capture images. The
    expensive model work remains behind explicit later steps.
    """

    SESSION_PREFIX = "kiosk-session:v1:"

    def __init__(
        self,
        session_dir: str | Path,
        capture_analyzer: Any | None = None,
        garment_registry: Any | None = None,
    ) -> None:
        self.session_dir = Path(session_dir)
        self.sessions_dir = self.session_dir / "sessions"
        self.captures_dir = self.session_dir / "captures"
        self.capture_analyzer = capture_analyzer
        self.garment_registry = garment_registry
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.captures_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        *,
        garment_id: str | None,
        avatar_cache_key: str | None = None,
        avatar_preview_cache_key: str | None = None,
    ) -> KioskTryOnSession:
        if garment_id and self.garment_registry is not None:
            if not self.garment_registry.exists(garment_id):
                raise FileNotFoundError(f"Garment not found: {garment_id}")

        now = _utc_now()
        session = KioskTryOnSession(
            session_id=f"{self.SESSION_PREFIX}{uuid4().hex}",
            status=(
                "avatar_preview_ready"
                if avatar_preview_cache_key
                else "awaiting_user_capture"
            ),
            garment_id=garment_id,
            avatar_cache_key=avatar_cache_key,
            avatar_preview_cache_key=avatar_preview_cache_key,
            created_at=now,
            updated_at=now,
        )
        self._write_session(session)
        return session

    def get_session(self, session_id: str) -> KioskTryOnSession:
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Kiosk session not found: {session_id}")
        return self._read_session(path)

    def add_user_capture(
        self,
        *,
        session_id: str,
        front_image: bytes,
        side_image: bytes | None = None,
        capture_source: str | None = None,
        capture_metadata: dict[str, Any] | None = None,
    ) -> KioskTryOnSession:
        session = self.get_session(session_id)
        safe_session_id = _safe_filename(session.session_id)
        normalized_capture_source = _normalize_capture_source(capture_source)
        normalized_capture_metadata = _normalize_capture_metadata(capture_metadata)

        captures: dict[str, dict[str, Any]] = dict(session.captures)
        capture_keys: list[str] = []

        front_path = self._write_capture(
            filename=f"{safe_session_id}-front.png",
            image_bytes=front_image,
            field_name="front_image",
        )
        captures["front"] = _capture_payload(
            path=self._relative_path(front_path),
            capture_source=normalized_capture_source,
            capture_metadata=normalized_capture_metadata.get("front"),
        )
        capture_keys.append("front")

        if side_image is not None:
            side_path = self._write_capture(
                filename=f"{safe_session_id}-side.png",
                image_bytes=side_image,
                field_name="side_image",
            )
            captures["side"] = _capture_payload(
                path=self._relative_path(side_path),
                capture_source=normalized_capture_source,
                capture_metadata=normalized_capture_metadata.get("side"),
            )
            capture_keys.append("side")

        updated = KioskTryOnSession(
            session_id=session.session_id,
            status="user_captured",
            garment_id=session.garment_id,
            avatar_cache_key=session.avatar_cache_key,
            avatar_preview_cache_key=session.avatar_preview_cache_key,
            capture_keys=capture_keys,
            captures=captures,
            capture_analysis=session.capture_analysis,
            personalized_tryon_key=session.personalized_tryon_key,
            fit_analysis_key=session.fit_analysis_key,
            created_at=session.created_at,
            updated_at=_utc_now(),
        )
        self._write_session(updated)
        return updated

    def analyze_user_capture(self, *, session_id: str) -> KioskTryOnSession:
        if self.capture_analyzer is None:
            raise RuntimeError("Kiosk capture analyzer is not configured")

        session = self.get_session(session_id)
        front_capture = session.captures.get("front")
        if not front_capture or not front_capture.get("path"):
            raise ValueError("front capture is required before analysis")

        front_path = self.session_dir / front_capture["path"]
        image_bytes = front_path.read_bytes()
        garment_category = self._garment_category_for_session(session)
        analysis = _normalize_analysis_result(
            _analyze_front_capture(
                self.capture_analyzer,
                image_bytes=image_bytes,
                garment_category=garment_category,
            )
        )
        capture_source = _capture_source_from_session(session)
        capture_metadata = _capture_metadata_from_session(session, "front")
        if capture_source:
            analysis = {
                **analysis,
                "capture_source": capture_source,
                "capture_source_quality": _capture_source_quality(
                    capture_source,
                    capture_metadata=capture_metadata,
                ),
            }
        if capture_metadata:
            analysis = {
                **analysis,
                "capture_metadata": capture_metadata,
                "capture_protocol_quality": _capture_protocol_quality(capture_metadata),
            }
        status = (
            "capture_analysis_passed"
            if bool(analysis.get("passed"))
            else "needs_recapture"
        )

        updated = KioskTryOnSession(
            session_id=session.session_id,
            status=status,
            garment_id=session.garment_id,
            avatar_cache_key=session.avatar_cache_key,
            avatar_preview_cache_key=session.avatar_preview_cache_key,
            capture_keys=session.capture_keys,
            captures=session.captures,
            capture_analysis=analysis,
            personalized_tryon_key=session.personalized_tryon_key,
            fit_analysis_key=session.fit_analysis_key,
            created_at=session.created_at,
            updated_at=_utc_now(),
        )
        self._write_session(updated)
        return updated

    def read_capture_image(self, *, session_id: str, capture_key: str) -> bytes:
        session = self.get_session(session_id)
        capture = session.captures.get(capture_key)
        if not capture or not capture.get("path"):
            raise ValueError(f"{capture_key} capture is not available")

        path = self.session_dir / capture["path"]
        if not path.exists():
            raise FileNotFoundError(f"Kiosk capture file not found: {capture_key}")
        return path.read_bytes()

    def mark_personalized_tryon_ready(
        self,
        *,
        session_id: str,
        personalized_tryon_key: str,
    ) -> KioskTryOnSession:
        session = self.get_session(session_id)
        if not personalized_tryon_key.strip():
            raise ValueError("personalized_tryon_key must not be empty")

        updated = KioskTryOnSession(
            session_id=session.session_id,
            status="personalized_tryon_ready",
            garment_id=session.garment_id,
            avatar_cache_key=session.avatar_cache_key,
            avatar_preview_cache_key=session.avatar_preview_cache_key,
            capture_keys=session.capture_keys,
            captures=session.captures,
            capture_analysis=session.capture_analysis,
            personalized_tryon_key=personalized_tryon_key,
            fit_analysis_key=session.fit_analysis_key,
            created_at=session.created_at,
            updated_at=_utc_now(),
        )
        self._write_session(updated)
        return updated

    def mark_fit_analysis_ready(
        self,
        *,
        session_id: str,
        fit_analysis_key: str,
    ) -> KioskTryOnSession:
        session = self.get_session(session_id)
        if not fit_analysis_key.strip():
            raise ValueError("fit_analysis_key must not be empty")

        updated = KioskTryOnSession(
            session_id=session.session_id,
            status="fit_analysis_ready",
            garment_id=session.garment_id,
            avatar_cache_key=session.avatar_cache_key,
            avatar_preview_cache_key=session.avatar_preview_cache_key,
            capture_keys=session.capture_keys,
            captures=session.captures,
            capture_analysis=session.capture_analysis,
            personalized_tryon_key=session.personalized_tryon_key,
            fit_analysis_key=fit_analysis_key,
            created_at=session.created_at,
            updated_at=_utc_now(),
        )
        self._write_session(updated)
        return updated

    def _write_capture(
        self,
        *,
        filename: str,
        image_bytes: bytes,
        field_name: str,
    ) -> Path:
        if not image_bytes:
            raise ValueError(f"{field_name} must not be empty")

        path = self.captures_dir / filename
        path.write_bytes(image_bytes)
        return path

    def _write_session(self, session: KioskTryOnSession) -> None:
        path = self._session_path(session.session_id)
        path.write_text(
            json.dumps(asdict(session), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _read_session(self, path: Path) -> KioskTryOnSession:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return KioskTryOnSession(
            session_id=str(payload["session_id"]),
            status=str(payload["status"]),
            garment_id=payload.get("garment_id"),
            avatar_cache_key=payload.get("avatar_cache_key"),
            avatar_preview_cache_key=payload.get("avatar_preview_cache_key"),
            capture_keys=list(payload.get("capture_keys", [])),
            captures=dict(payload.get("captures", {})),
            capture_analysis=payload.get("capture_analysis"),
            personalized_tryon_key=payload.get("personalized_tryon_key"),
            fit_analysis_key=payload.get("fit_analysis_key"),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
        )

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{_safe_filename(session_id)}.json"

    def _relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.session_dir))

    def _garment_category_for_session(self, session: KioskTryOnSession) -> str | None:
        if not session.garment_id or self.garment_registry is None:
            return None
        get_garment = getattr(self.garment_registry, "get_garment", None)
        if get_garment is None:
            return None
        garment = get_garment(session.garment_id)
        if garment is None:
            return None
        if isinstance(garment, dict):
            category = garment.get("category")
        else:
            category = getattr(garment, "category", None)
        return str(category) if category else None


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "-" for char in value)


def _capture_payload(
    *,
    path: str,
    capture_source: str | None,
    capture_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": path}
    if capture_source:
        payload["source"] = capture_source
    if capture_metadata:
        payload["metadata"] = capture_metadata
    return payload


def _normalize_capture_source(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^a-z0-9_.-]+", "_", value.strip().lower()).strip("_")
    return normalized[:64] or None


def _capture_source_from_session(session: KioskTryOnSession) -> str | None:
    front_capture = session.captures.get("front") or {}
    source = front_capture.get("source")
    return str(source) if source else None


def _capture_metadata_from_session(
    session: KioskTryOnSession,
    capture_key: str,
) -> dict[str, Any] | None:
    capture = session.captures.get(capture_key) or {}
    metadata = capture.get("metadata")
    return metadata if isinstance(metadata, dict) else None


def _capture_source_quality(
    capture_source: str,
    *,
    capture_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    guided = capture_source in {"guided_mobile_web", "kiosk_webcam"}
    protocol_quality = (
        _capture_protocol_quality(capture_metadata) if capture_metadata else {}
    )
    return {
        "guided_capture": guided,
        "protocol_quality": protocol_quality,
        "confidence_policy": (
            "Capture source is trace metadata only; size confidence still requires "
            "calibrated measurements or a validated estimator."
        ),
    }


def _normalize_capture_metadata(
    metadata: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(metadata, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for key in ("front", "side"):
        value = metadata.get(key)
        if isinstance(value, dict):
            normalized[key] = _sanitize_capture_metadata(value)
    return normalized


def _sanitize_capture_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed_scalar_keys = {
        "slot",
        "source",
        "protocol_version",
        "capture_mode",
        "burst_count",
        "selected_frame_index",
        "selected_frame_score",
        "video_width",
        "video_height",
        "captured_at",
    }
    sanitized: dict[str, Any] = {}
    for key in allowed_scalar_keys:
        value = metadata.get(key)
        if isinstance(value, str):
            sanitized[key] = value[:128]
        elif isinstance(value, int | float | bool):
            sanitized[key] = value

    metrics = metadata.get("selected_frame_metrics")
    if isinstance(metrics, dict):
        sanitized["selected_frame_metrics"] = {
            str(key)[:64]: value
            for key, value in metrics.items()
            if isinstance(value, int | float | bool | str)
        }
    return sanitized


def _capture_protocol_quality(metadata: dict[str, Any]) -> dict[str, Any]:
    mode = str(metadata.get("capture_mode") or "")
    burst_count = _safe_float(metadata.get("burst_count"))
    selected_frame_score = _safe_float(metadata.get("selected_frame_score"))
    guided_burst = mode == "countdown_scan_burst" and burst_count >= 3
    selected_frame_ready = selected_frame_score >= 0.75
    return {
        "guided_burst_capture": guided_burst,
        "selected_frame_ready": selected_frame_ready,
        "selected_frame_score": round(selected_frame_score, 4),
        "burst_count": int(burst_count) if burst_count else 0,
        "target_confidence_signal": guided_burst and selected_frame_ready,
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_analysis_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return dict(result.model_dump(mode="json"))
    if is_dataclass_instance(result):
        return dict(asdict(result))
    raise TypeError(f"Unsupported capture analysis result type: {type(result)}")


def _analyze_front_capture(
    capture_analyzer: Any,
    *,
    image_bytes: bytes,
    garment_category: str | None,
) -> Any:
    method = capture_analyzer.analyze_front_capture
    try:
        accepts_garment_category = (
            "garment_category" in inspect.signature(method).parameters
        )
    except (TypeError, ValueError):
        accepts_garment_category = False
    if accepts_garment_category:
        return method(image_bytes, garment_category=garment_category)
    return method(image_bytes)


def is_dataclass_instance(value: Any) -> bool:
    return hasattr(value, "__dataclass_fields__") and not isinstance(value, type)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
