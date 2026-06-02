"""
Persistent session state for the kiosk try-on flow.

The kiosk flow is intentionally staged:
1. preview a garment on a synthetic avatar;
2. create a kiosk session from that approved avatar preview;
3. capture user photos for the later personalized try-on step.
"""

from __future__ import annotations

import base64
import json
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
    avatar_cache_key: str
    avatar_preview_cache_key: str
    capture_keys: list[str] = field(default_factory=list)
    captures: dict[str, dict[str, str]] = field(default_factory=dict)
    capture_analysis: dict[str, Any] | None = None
    personalized_tryon_key: str | None = None
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
    ) -> None:
        self.session_dir = Path(session_dir)
        self.sessions_dir = self.session_dir / "sessions"
        self.captures_dir = self.session_dir / "captures"
        self.capture_analyzer = capture_analyzer
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.captures_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        *,
        garment_id: str | None,
        avatar_cache_key: str,
        avatar_preview_cache_key: str,
    ) -> KioskTryOnSession:
        now = _utc_now()
        session = KioskTryOnSession(
            session_id=f"{self.SESSION_PREFIX}{uuid4().hex}",
            status="avatar_preview_ready",
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
        front_image: str,
        side_image: str | None = None,
    ) -> KioskTryOnSession:
        session = self.get_session(session_id)
        safe_session_id = _safe_filename(session.session_id)

        captures: dict[str, dict[str, str]] = dict(session.captures)
        capture_keys: list[str] = []

        front_path = self._write_capture(
            filename=f"{safe_session_id}-front.png",
            image_b64=front_image,
            field_name="front_image",
        )
        captures["front"] = {"path": self._relative_path(front_path)}
        capture_keys.append("front")

        if side_image is not None:
            side_path = self._write_capture(
                filename=f"{safe_session_id}-side.png",
                image_b64=side_image,
                field_name="side_image",
            )
            captures["side"] = {"path": self._relative_path(side_path)}
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
        analysis = _normalize_analysis_result(
            self.capture_analyzer.analyze_front_capture(image_bytes)
        )
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
            created_at=session.created_at,
            updated_at=_utc_now(),
        )
        self._write_session(updated)
        return updated

    def _write_capture(
        self,
        *,
        filename: str,
        image_b64: str,
        field_name: str,
    ) -> Path:
        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
        except Exception as exc:
            raise ValueError(f"{field_name} must be valid base64") from exc

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
            avatar_cache_key=str(payload["avatar_cache_key"]),
            avatar_preview_cache_key=str(payload["avatar_preview_cache_key"]),
            capture_keys=list(payload.get("capture_keys", [])),
            captures=dict(payload.get("captures", {})),
            capture_analysis=payload.get("capture_analysis"),
            personalized_tryon_key=payload.get("personalized_tryon_key"),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
        )

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{_safe_filename(session_id)}.json"

    def _relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.session_dir))


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "-" for char in value)


def _normalize_analysis_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return dict(result.model_dump(mode="json"))
    if is_dataclass_instance(result):
        return dict(asdict(result))
    raise TypeError(f"Unsupported capture analysis result type: {type(result)}")


def is_dataclass_instance(value: Any) -> bool:
    return hasattr(value, "__dataclass_fields__") and not isinstance(value, type)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
