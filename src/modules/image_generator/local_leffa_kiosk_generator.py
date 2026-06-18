"""Local Leffa adapter for kiosk visual preview jobs."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.modules.image_generator.base import ImageGeneratorBase


class LocalLeffaKioskGenerator(ImageGeneratorBase):
    """Run Leffa as the self-hosted visual preview engine for kiosk garments."""

    PROMPT_VERSION = "local-leffa-category-conditioned-v1"
    INPUT_MAPPING = "category_conditioned_leffa"

    def __init__(
        self,
        *,
        work_dir: Path,
        leffa_root: Path,
        repo_url: str,
        model_repo_id: str,
        checkpoint_dir: Path,
        python_executable: Path | None = None,
        hf_home: Path | None = None,
        torch_home: Path | None = None,
        xdg_cache_home: Path | None = None,
        no_clone: bool = True,
        size: str = "768x1024",
        device: str = "cuda",
        dtype: str = "float16",
        vt_model_type: str = "viton_hd",
        steps: int = 30,
        guidance_scale: float = 2.5,
        seed: int = 42,
        timeout_seconds: int = 900,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.leffa_root = Path(leffa_root)
        self.repo_url = repo_url
        self.model_repo_id = model_repo_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.python_executable = Path(python_executable) if python_executable else None
        self.hf_home = Path(hf_home) if hf_home else None
        self.torch_home = Path(torch_home) if torch_home else None
        self.xdg_cache_home = Path(xdg_cache_home) if xdg_cache_home else None
        self.no_clone = no_clone
        self.size = size
        self.device = device
        self.dtype = dtype
        self.vt_model_type = vt_model_type
        self.steps = steps
        self.guidance_scale = guidance_scale
        self.seed = seed
        self.timeout_seconds = timeout_seconds
        self._last_generation_metadata: dict[str, Any] = {}
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "preview_model": (
                f"Leffa:{self.model_repo_id}:{self.vt_model_type}:"
                f"{self.size}:steps{self.steps}:cfg{self.guidance_scale}"
            ),
            "preview_input_mapping": self.INPUT_MAPPING,
            "preview_prompt_version": self.PROMPT_VERSION,
        }

    def get_last_generation_metadata(self) -> dict[str, Any]:
        return dict(self._last_generation_metadata)

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: bytes | None = None,
        size: str = "1024x1024",
    ) -> bytes:
        generated = self.generate_kiosk_tryon(
            user_image=base_image,
            garment_image=garment_image,
            prompt=inpainting_prompt,
            garment_category="tops",
            garment_type=None,
            session_id="local-leffa-direct",
            garment_id="local-leffa-direct",
            size=size,
        )
        return _decode_base64(generated, field_name="generated_image")

    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: str | None = None,
        size: str = "1024x1024",
    ) -> str:
        return self.generate_kiosk_tryon(
            user_image=_decode_base64(base_image_b64, field_name="base_image_b64"),
            garment_image=_decode_base64(
                garment_image_b64,
                field_name="garment_image_b64",
            ),
            prompt=inpainting_prompt,
            garment_category="tops",
            garment_type=None,
            session_id="local-leffa-direct",
            garment_id="local-leffa-direct",
            size=size,
        )

    def generate_kiosk_tryon(
        self,
        *,
        user_image: bytes,
        garment_image: bytes,
        prompt: str,
        garment_category: str,
        garment_type: str | None,
        session_id: str,
        garment_id: str,
        size: str,
    ) -> str:
        normalized_category = _normalize_category(garment_category)
        category_config = _leffa_category_config(normalized_category)

        digest = hashlib.sha256(
            b"|".join(
                [
                    session_id.encode("utf-8"),
                    garment_id.encode("utf-8"),
                    normalized_category.encode("utf-8"),
                    (garment_type or "").encode("utf-8"),
                    user_image,
                    garment_image,
                    prompt.encode("utf-8"),
                    self.get_runtime_metadata()["preview_model"].encode("utf-8"),
                    category_config.leffa_garment_type.encode("utf-8"),
                    category_config.person_framing.encode("utf-8"),
                ]
            )
        ).hexdigest()
        work_dir = self.work_dir / digest[:32]
        work_dir.mkdir(parents=True, exist_ok=True)

        source_person = work_dir / "person-source.png"
        source_garment = work_dir / "garment-source.png"
        conditioned_person = work_dir / "person-conditioned.png"
        conditioned_garment = work_dir / "garment-conditioned.png"
        input_quality_report = work_dir / "input-quality.json"
        conditioning_report = work_dir / "conditioning.json"
        output = work_dir / "leffa-output.png"
        leffa_report = work_dir / "leffa-report.json"

        source_person.write_bytes(user_image)
        source_garment.write_bytes(garment_image)

        started = time.time()
        input_quality = _score_inputs(
            person_image=source_person,
            garment_image=source_garment,
            garment_category=category_config.quality_category,
        )
        input_quality_report.write_text(
            json.dumps(input_quality, indent=2, sort_keys=True),
            "utf-8",
        )

        conditioning = _condition_inputs(
            person_image=source_person,
            garment_image=source_garment,
            person_output=conditioned_person,
            garment_output=conditioned_garment,
            report=conditioning_report,
            person_framing=category_config.person_framing,
        )

        command = [
            str(self.python_executable or sys.executable),
            "-m",
            "scripts.local_leffa_smoke",
            "--person-image",
            str(conditioned_person),
            "--garment-image",
            str(conditioned_garment),
            "--output",
            str(output),
            "--report",
            str(leffa_report),
            "--leffa-root",
            str(self.leffa_root),
            "--repo-url",
            self.repo_url,
            "--model-repo-id",
            self.model_repo_id,
            "--checkpoint-dir",
            str(self.checkpoint_dir),
            "--size",
            self.size,
            "--device",
            self.device,
            "--dtype",
            self.dtype,
            "--vt-model-type",
            self.vt_model_type,
            "--garment-type",
            category_config.leffa_garment_type,
            "--steps",
            str(self.steps),
            "--guidance-scale",
            str(self.guidance_scale),
            "--seed",
            str(self.seed),
            "--no-ref-acceleration",
            "--no-repaint",
            "--no-preprocess-garment",
        ]
        if self.no_clone:
            command.append("--no-clone")

        completed = subprocess.run(
            command,
            cwd=_project_root(),
            env=self._subprocess_env(),
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Local Leffa generation failed "
                f"(exit={completed.returncode}). "
                f"stdout={completed.stdout[-1200:]} stderr={completed.stderr[-1200:]}"
            )
        if not output.exists():
            raise RuntimeError(f"Local Leffa did not write output: {output}")

        leffa_payload = _read_json(leffa_report)
        self._last_generation_metadata = {
            "provider": "local_leffa",
            "garment_category": normalized_category,
            "garment_type": garment_type,
            "leffa_garment_type": category_config.leffa_garment_type,
            "person_framing": category_config.person_framing,
            "quality_category": category_config.quality_category,
            "quality_gate_status": category_config.quality_gate_status,
            "requested_size": size,
            "effective_size": self.size,
            "work_dir": str(work_dir),
            "source_person": str(source_person),
            "source_garment": str(source_garment),
            "conditioned_person": str(conditioned_person),
            "conditioned_garment": str(conditioned_garment),
            "input_quality_report": str(input_quality_report),
            "conditioning_report": str(conditioning_report),
            "leffa_report": str(leffa_report),
            "input_quality": input_quality,
            "conditioning": conditioning,
            "leffa": leffa_payload,
            "generation_time_seconds": time.time() - started,
            "warnings": _metadata_warnings(
                input_quality=input_quality,
                category_config=category_config,
            ),
        }
        return base64.b64encode(output.read_bytes()).decode("utf-8")

    def _subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        if self.hf_home:
            env["HF_HOME"] = str(self.hf_home)
            env["TRANSFORMERS_CACHE"] = str(self.hf_home / "transformers")
            env["HUGGINGFACE_HUB_CACHE"] = str(self.hf_home / "hub")
        if self.torch_home:
            env["TORCH_HOME"] = str(self.torch_home)
        if self.xdg_cache_home:
            env["XDG_CACHE_HOME"] = str(self.xdg_cache_home)
        return env


def _score_inputs(
    *,
    person_image: Path,
    garment_image: Path,
    garment_category: str,
) -> dict[str, Any]:
    from scripts.score_vton_input_quality import score_inputs

    return score_inputs(
        person_image=person_image,
        garment_image=garment_image,
        garment_category=garment_category,
        background=(250, 250, 250),
        foreground_threshold=28.0,
    )


def _condition_inputs(
    *,
    person_image: Path,
    garment_image: Path,
    person_output: Path,
    garment_output: Path,
    report: Path,
    person_framing: str,
) -> dict[str, Any]:
    from scripts.prepare_vton_conditioned_inputs import prepare_conditioned_inputs

    return prepare_conditioned_inputs(
        person_image=person_image,
        garment_image=garment_image,
        person_output=person_output,
        garment_output=garment_output,
        report=report,
        person_max_size=1024,
        person_canvas_size=(768, 1024),
        person_border_ratio=0.06,
        person_framing=person_framing,
        garment_canvas_size=1024,
        garment_border_ratio=0.08,
        garment_largest_component=True,
        background=(250, 250, 250),
        foreground_threshold=28.0,
        person_clean_background=True,
        person_enhance=True,
        garment_enhance=True,
    )


def _metadata_warnings(
    *,
    input_quality: dict[str, Any],
    category_config: "_LeffaCategoryConfig",
) -> list[str]:
    warnings: list[str] = []
    if not bool(input_quality.get("passed")):
        recommendation = input_quality.get("recommendation")
        if isinstance(recommendation, str) and recommendation:
            warnings.append(f"input quality gate warning: {recommendation}")
    if category_config.quality_gate_status != "baseline_passed":
        warnings.append(
            "local Leffa category is enabled for quality-gate testing, "
            f"not production baseline: {category_config.quality_gate_status}"
        )
    return warnings


@dataclass(frozen=True)
class _LeffaCategoryConfig:
    normalized_category: str
    leffa_garment_type: str
    quality_category: str
    person_framing: str
    quality_gate_status: str


def _leffa_category_config(category: str) -> _LeffaCategoryConfig:
    if category == "tops":
        return _LeffaCategoryConfig(
            normalized_category=category,
            leffa_garment_type="upper_body",
            quality_category="tops",
            person_framing="upper_body",
            quality_gate_status="baseline_passed",
        )
    if category == "bottoms":
        return _LeffaCategoryConfig(
            normalized_category=category,
            leffa_garment_type="lower_body",
            quality_category="bottoms",
            person_framing="full_body",
            quality_gate_status="experimental_needs_manual_review",
        )
    if category in {"one_pieces", "dress", "full_outfit"}:
        return _LeffaCategoryConfig(
            normalized_category=category,
            leffa_garment_type="dresses",
            quality_category="dress" if category != "full_outfit" else "full_outfit",
            person_framing="full_body",
            quality_gate_status="experimental_needs_manual_review",
        )
    raise ValueError(
        "Local Leffa kiosk preview supports tops, bottoms, one_pieces, and "
        f"full_outfit/dress aliases. Received garment_category={category!r}."
    )


def _normalize_category(category: str) -> str:
    normalized = category.strip().lower().replace("-", "_")
    aliases = {
        "top": "tops",
        "shirt": "tops",
        "t_shirt": "tops",
        "upper": "tops",
        "upper_body": "tops",
        "bottom": "bottoms",
        "pants": "bottoms",
        "shorts": "bottoms",
        "lower": "bottoms",
        "lower_body": "bottoms",
        "outfit": "full_outfit",
        "full_body": "full_outfit",
        "top_and_bottom": "full_outfit",
        "one_piece": "one_pieces",
        "dress": "dress",
        "dresses": "dress",
    }
    return aliases.get(normalized, normalized)


def _decode_base64(payload: str, *, field_name: str) -> bytes:
    if not payload:
        raise ValueError(f"{field_name} must not be empty")
    normalized = payload.strip()
    if normalized.startswith("data:"):
        normalized = normalized.split("base64,", 1)[1]
    return base64.b64decode(normalized, validate=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]
