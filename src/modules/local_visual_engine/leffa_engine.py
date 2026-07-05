from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.modules.local_visual_engine.contracts import (
    EngineMetadata,
    GenerateRequest,
    GenerateResult,
)


@dataclass
class _LoadedState:
    modules: dict[str, Any]
    checkpoint_dir: Path
    checkpoint_assets: dict[str, str]
    densepose: Any
    parsing: Any
    openpose: Any
    model: Any
    inference: Any
    transform: Any


class LeffaVisualEngine:
    def __init__(
        self,
        *,
        leffa_root: Path | str,
        repo_url: str,
        no_clone: bool,
        model_repo_id: str,
        checkpoint_dir: Path | str,
        size: str,
        device: str,
        dtype: str,
        vt_model_type: str,
        allow_tf32: bool = True,
    ) -> None:
        self.leffa_root = Path(leffa_root)
        self.repo_url = repo_url
        self.no_clone = no_clone
        self.model_repo_id = model_repo_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.size = size
        self.device = device
        self.dtype = dtype
        self.vt_model_type = vt_model_type
        self.allow_tf32 = allow_tf32
        self._state: _LoadedState | None = None
        self._metadata: EngineMetadata | None = None
        self._resolved_device: str | None = None

    def load(self) -> EngineMetadata:
        if self._state is not None and self._metadata is not None:
            return self._metadata

        width, height = self._validate_size()
        self._resolved_device = resolve_device(self.device)
        validate_device_runtime(self._resolved_device)
        self._configure_tf32()
        ensure_leffa_repo(
            leffa_root=self.leffa_root,
            repo_url=self.repo_url,
            no_clone=self.no_clone,
        )
        modules = load_leffa_modules(self.leffa_root)
        download_leffa_checkpoints(
            modules=modules,
            model_repo_id=self.model_repo_id,
            ckpt_dir=self.checkpoint_dir,
        )
        checkpoint_assets = validate_leffa_checkpoint_assets(
            ckpt_dir=self.checkpoint_dir,
            vt_model_type=self.vt_model_type,
        )

        densepose = modules["DensePosePredictor"](
            config_path=str(
                self.checkpoint_dir / "densepose" / "densepose_rcnn_R_50_FPN_s1x.yaml"
            ),
            weights_path=str(
                self.checkpoint_dir / "densepose" / "model_final_162be9.pkl"
            ),
        )
        parsing = modules["Parsing"](
            atr_path=str(self.checkpoint_dir / "humanparsing" / "parsing_atr.onnx"),
            lip_path=str(self.checkpoint_dir / "humanparsing" / "parsing_lip.onnx"),
        )
        openpose = modules["OpenPose"](
            body_model_path=str(
                self.checkpoint_dir / "openpose" / "body_pose_model.pth"
            ),
        )
        model = modules["LeffaModel"](
            pretrained_model_name_or_path=checkpoint_assets["base_model_path"],
            pretrained_model=checkpoint_assets["virtual_tryon_checkpoint"],
            dtype=self.dtype,
        )
        inference = modules["LeffaInference"](model=model)
        transform = modules["LeffaTransform"]()

        self._state = _LoadedState(
            modules=modules,
            checkpoint_dir=self.checkpoint_dir,
            checkpoint_assets=checkpoint_assets,
            densepose=densepose,
            parsing=parsing,
            openpose=openpose,
            model=model,
            inference=inference,
            transform=transform,
        )
        self._metadata = self._build_metadata(width=width, height=height)
        return self._metadata

    def is_ready(self) -> bool:
        return self._state is not None

    def metadata(self) -> EngineMetadata:
        if self._metadata is None:
            width, height = self._validate_size()
            return self._build_metadata(width=width, height=height)
        return self._metadata

    def generate(self, request: GenerateRequest) -> GenerateResult:
        if self._state is None:
            raise RuntimeError("LeffaVisualEngine is not loaded")
        if request.engine != "leffa":
            raise ValueError(
                f"LeffaVisualEngine cannot generate engine {request.engine!r}"
            )

        started_at = datetime.now(UTC)
        started_monotonic = time.perf_counter()
        width, height = self._validate_request_size(request)
        output = Path(request.output)
        report = Path(request.report)
        person_image = Path(request.person_image)
        garment_image = Path(request.garment_image)

        ensure_input_exists(person_image, "person image")
        ensure_input_exists(garment_image, "garment image")

        src_image = _load_rgb_image(person_image)
        src_image = self._state.modules["resize_and_center"](src_image, width, height)
        if request.preprocess_garment:
            ref_image = self._state.modules["preprocess_garment_image"](
                str(garment_image)
            )
        else:
            ref_image = _load_rgb_image(garment_image)
        ref_image = self._state.modules["resize_and_center"](ref_image, width, height)

        src_image_array = np.array(src_image)
        src_image = src_image.convert("RGB")
        model_parse, _ = self._state.parsing(src_image.resize((384, 512)))
        keypoints = self._state.openpose(src_image.resize((384, 512)))
        mask, densepose = self._build_mask_and_densepose(
            model_parse=model_parse,
            keypoints=keypoints,
            garment_type=request.garment_type,
            src_image_array=src_image_array,
        )
        mask = mask.resize((width, height))

        data = {
            "src_image": [src_image],
            "ref_image": [ref_image],
            "mask": [mask],
            "densepose": [densepose],
        }
        data = self._state.transform(data)

        import torch

        if self._active_device() == "cuda":
            try:
                torch.cuda.reset_peak_memory_stats()
            except Exception:
                pass

        with torch.inference_mode():
            inference_output = self._state.inference(
                data,
                ref_acceleration=request.ref_acceleration,
                num_inference_steps=request.steps,
                guidance_scale=request.guidance_scale,
                seed=request.seed,
                repaint=request.repaint,
            )
        generated_image = inference_output["generated_image"][0]

        output.parent.mkdir(parents=True, exist_ok=True)
        generated_image.save(output)
        mask_output = output.with_name(f"{output.stem}-mask.png")
        densepose_output = output.with_name(f"{output.stem}-densepose.png")
        mask.save(mask_output)
        densepose.save(densepose_output)

        generation_time_seconds = time.perf_counter() - started_monotonic
        report_payload = self._build_report_payload(
            request=request,
            output=output,
            report=report,
            mask_output=mask_output,
            densepose_output=densepose_output,
            started_at=started_at,
            generation_time_seconds=generation_time_seconds,
            width=width,
            height=height,
        )
        _write_report(report, report_payload)

        return GenerateResult(
            success=True,
            engine="leffa",
            output=str(output),
            report=str(report),
            artifacts={
                "mask_output": str(mask_output),
                "densepose_output": str(densepose_output),
            },
            generation_time_seconds=generation_time_seconds,
            engine_metadata=self.metadata().to_dict(),
        )

    def _validate_size(self) -> tuple[int, int]:
        width, height = parse_size(self.size)
        if (width, height) != (768, 1024):
            raise ValueError(
                "Leffa upstream inference expects 768x1024. "
                f"Got {self.size}; use size='768x1024'."
            )
        return width, height

    def _validate_request_size(self, request: GenerateRequest) -> tuple[int, int]:
        width, height = parse_size(request.size)
        if (width, height) != parse_size(self.size):
            raise ValueError(
                f"Request size {request.size!r} does not match loaded size "
                f"{self.size!r}"
            )
        return self._validate_size()

    def _configure_tf32(self) -> None:
        if not self.allow_tf32 or self._active_device() != "cuda":
            return

        import torch

        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    def _build_metadata(self, *, width: int, height: int) -> EngineMetadata:
        checkpoint_assets = self._state.checkpoint_assets if self._state else {}
        return EngineMetadata(
            engine="leffa",
            implementation="LeffaVisualEngine",
            model_repo_id=self.model_repo_id,
            checkpoint_dir=str(self.checkpoint_dir),
            device=self._active_device(),
            dtype=self.dtype,
            model_type=self.vt_model_type,
            extra={
                "size": self.size,
                "width": width,
                "height": height,
                "leffa_root": str(self.leffa_root),
                "base_model_path": checkpoint_assets.get("base_model_path"),
                "pretrained_model": checkpoint_assets.get("virtual_tryon_checkpoint"),
            },
        )

    def _build_mask_and_densepose(
        self,
        *,
        model_parse: Any,
        keypoints: Any,
        garment_type: str,
        src_image_array: np.ndarray,
    ) -> tuple[Image.Image, Image.Image]:
        if self._state is None:
            raise RuntimeError("LeffaVisualEngine is not loaded")

        if self.vt_model_type == "viton_hd":
            mask = self._state.modules["get_agnostic_mask_hd"](
                model_parse,
                keypoints,
                garment_type,
            )
            src_image_seg_array = self._state.densepose.predict_seg(src_image_array)[
                :, :, ::-1
            ]
            return mask, Image.fromarray(src_image_seg_array)

        mask = self._state.modules["get_agnostic_mask_dc"](
            model_parse,
            keypoints,
            garment_type,
        )
        src_image_iuv_array = self._state.densepose.predict_iuv(src_image_array)
        src_image_seg_array = src_image_iuv_array[:, :, 0:1]
        src_image_seg_array = np.concatenate([src_image_seg_array] * 3, axis=-1)
        return mask, Image.fromarray(src_image_seg_array)

    def _build_report_payload(
        self,
        *,
        request: GenerateRequest,
        output: Path,
        report: Path,
        mask_output: Path,
        densepose_output: Path,
        started_at: datetime,
        generation_time_seconds: float,
        width: int,
        height: int,
    ) -> dict[str, Any]:
        metadata = self.metadata().to_dict()
        return {
            "success": True,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "generation_time_seconds": generation_time_seconds,
            "execution_mode": "service",
            "model": "Leffa",
            "repo_url": self.repo_url,
            "model_repo_id": self.model_repo_id,
            "leffa_root": str(self.leffa_root),
            "checkpoint_dir": str(self.checkpoint_dir),
            "base_model_path": metadata["extra"]["base_model_path"],
            "pretrained_model": metadata["extra"]["pretrained_model"],
            "device": self._active_device(),
            "dtype": self.dtype,
            "size": self.size,
            "width": width,
            "height": height,
            "vt_model_type": self.vt_model_type,
            "garment_type": request.garment_type,
            "steps": request.steps,
            "guidance_scale": request.guidance_scale,
            "seed": request.seed,
            "ref_acceleration": request.ref_acceleration,
            "repaint": request.repaint,
            "preprocess_garment": request.preprocess_garment,
            "allow_tf32": self.allow_tf32,
            "person_image": str(Path(request.person_image)),
            "garment_image": str(Path(request.garment_image)),
            "output": str(output),
            "mask_output": str(mask_output),
            "densepose_output": str(densepose_output),
            "report": str(report),
            "request": {
                "engine": request.engine,
                "person_image": request.person_image,
                "garment_image": request.garment_image,
                "output": request.output,
                "report": request.report,
                "garment_type": request.garment_type,
                "size": request.size,
                "steps": request.steps,
                "guidance_scale": request.guidance_scale,
                "seed": request.seed,
                "ref_acceleration": request.ref_acceleration,
                "repaint": request.repaint,
                "preprocess_garment": request.preprocess_garment,
            },
            "artifacts": {
                "mask_output": str(mask_output),
                "densepose_output": str(densepose_output),
            },
            "runtime": collect_runtime_metrics(self._active_device()),
            "engine_metadata": metadata,
            "error": None,
        }

    def _active_device(self) -> str:
        return self._resolved_device or self.device


def _smoke_helpers() -> Any:
    return import_module("scripts.local_leffa_smoke")


def collect_runtime_metrics(device: str) -> dict[str, Any]:
    return _smoke_helpers().collect_runtime_metrics(device)


def download_leffa_checkpoints(
    *,
    modules: dict[str, Any],
    model_repo_id: str,
    ckpt_dir: Path,
) -> None:
    _smoke_helpers().download_leffa_checkpoints(
        modules=modules,
        model_repo_id=model_repo_id,
        ckpt_dir=ckpt_dir,
    )


def ensure_input_exists(path: Path, label: str) -> None:
    _smoke_helpers().ensure_input_exists(path, label)


def ensure_leffa_repo(*, leffa_root: Path, repo_url: str, no_clone: bool) -> None:
    _smoke_helpers().ensure_leffa_repo(
        leffa_root=leffa_root,
        repo_url=repo_url,
        no_clone=no_clone,
    )


def load_leffa_modules(leffa_root: Path) -> dict[str, Any]:
    return _smoke_helpers().load_leffa_modules(leffa_root)


def parse_size(size: str) -> tuple[int, int]:
    return _smoke_helpers().parse_size(size)


def resolve_device(device: str) -> str:
    return _smoke_helpers().resolve_device(device)


def validate_device_runtime(device: str) -> None:
    _smoke_helpers().validate_device_runtime(device)


def validate_leffa_checkpoint_assets(
    *,
    ckpt_dir: Path,
    vt_model_type: str,
) -> dict[str, str]:
    return _smoke_helpers().validate_leffa_checkpoint_assets(
        ckpt_dir=ckpt_dir,
        vt_model_type=vt_model_type,
    )


def _load_rgb_image(path: Path) -> Image.Image:
    ensure_input_exists(path, "input image")
    with Image.open(path) as image:
        return image.convert("RGB")


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), "utf-8")
