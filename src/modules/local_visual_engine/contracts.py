from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class EngineMetadata:
    engine: str
    implementation: str
    model_repo_id: str
    checkpoint_dir: str
    device: str
    dtype: str
    model_type: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerateRequest:
    engine: str
    person_image: str
    garment_image: str
    output: str
    report: str
    garment_type: str
    size: str
    steps: int
    guidance_scale: float
    seed: int
    ref_acceleration: bool
    repaint: bool
    preprocess_garment: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GenerateRequest:
        required = {
            "engine",
            "person_image",
            "garment_image",
            "output",
            "report",
            "garment_type",
            "size",
            "steps",
            "guidance_scale",
            "seed",
            "ref_acceleration",
            "repaint",
            "preprocess_garment",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Missing generate request fields: {', '.join(missing)}")

        return cls(
            engine=str(payload["engine"]),
            person_image=str(payload["person_image"]),
            garment_image=str(payload["garment_image"]),
            output=str(payload["output"]),
            report=str(payload["report"]),
            garment_type=str(payload["garment_type"]),
            size=str(payload["size"]),
            steps=int(payload["steps"]),
            guidance_scale=float(payload["guidance_scale"]),
            seed=int(payload["seed"]),
            ref_acceleration=_as_bool(payload["ref_acceleration"]),
            repaint=_as_bool(payload["repaint"]),
            preprocess_garment=_as_bool(payload["preprocess_garment"]),
        )


@dataclass(frozen=True)
class GenerateResult:
    success: bool
    engine: str
    output: str
    report: str
    artifacts: dict[str, Any]
    generation_time_seconds: float
    engine_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VisualEngine(Protocol):
    def load(self) -> EngineMetadata:
        """Load persistent model state and return engine metadata."""
        ...

    def is_ready(self) -> bool:
        """Return whether the engine is loaded and ready for generation."""
        ...

    def metadata(self) -> EngineMetadata:
        """Return metadata for the active engine."""
        ...

    def generate(self, request: GenerateRequest) -> GenerateResult:
        """Generate one visual output."""
        ...


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
    raise ValueError(f"Cannot interpret {value!r} as a boolean")
