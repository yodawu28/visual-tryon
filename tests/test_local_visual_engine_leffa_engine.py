import json
from pathlib import Path

import numpy as np
from PIL import Image

from src.modules.local_visual_engine.contracts import GenerateRequest
from src.modules.local_visual_engine.leffa_engine import LeffaVisualEngine


class FakeDensePose:
    def __init__(self, *, config_path: str, weights_path: str) -> None:
        self.config_path = config_path
        self.weights_path = weights_path

    def predict_seg(self, image_array: np.ndarray) -> np.ndarray:
        return np.full_like(image_array, fill_value=80)


class FakeParsing:
    def __init__(self, *, atr_path: str, lip_path: str) -> None:
        self.atr_path = atr_path
        self.lip_path = lip_path

    def __call__(self, image: Image.Image) -> tuple[dict[str, str], None]:
        return {"parse": f"{image.size[0]}x{image.size[1]}"}, None


class FakeOpenPose:
    def __init__(self, *, body_model_path: str) -> None:
        self.body_model_path = body_model_path

    def __call__(self, image: Image.Image) -> dict[str, list[tuple[int, int]]]:
        return {"keypoints": [(image.size[0], image.size[1])]}


class FakeModel:
    def __init__(
        self,
        *,
        pretrained_model_name_or_path: str,
        pretrained_model: str,
        dtype: str,
    ) -> None:
        self.pretrained_model_name_or_path = pretrained_model_name_or_path
        self.pretrained_model = pretrained_model
        self.dtype = dtype


class FakeInference:
    def __init__(self, *, model: FakeModel) -> None:
        self.model = model
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        data: dict[str, object],
        *,
        ref_acceleration: bool,
        num_inference_steps: int,
        guidance_scale: float,
        seed: int,
        repaint: bool,
    ) -> dict[str, list[Image.Image]]:
        self.calls.append(
            {
                "data": data,
                "ref_acceleration": ref_acceleration,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "seed": seed,
                "repaint": repaint,
            }
        )
        return {"generated_image": [Image.new("RGB", (768, 1024), "blue")]}


class FakeTransform:
    def __call__(self, data: dict[str, object]) -> dict[str, object]:
        return {**data, "transformed": True}


def test_leffa_engine_loads_once_and_generates_artifacts(tmp_path, monkeypatch):
    import src.modules.local_visual_engine.leffa_engine as leffa_engine

    load_calls: list[Path] = []

    def fake_load_leffa_modules(leffa_root: Path) -> dict[str, object]:
        load_calls.append(leffa_root)
        return {
            "DensePosePredictor": FakeDensePose,
            "LeffaInference": FakeInference,
            "LeffaModel": FakeModel,
            "LeffaTransform": FakeTransform,
            "OpenPose": FakeOpenPose,
            "Parsing": FakeParsing,
            "get_agnostic_mask_hd": lambda *_: Image.new("L", (384, 512), 255),
            "preprocess_garment_image": lambda path: Image.open(path).convert("RGB"),
            "resize_and_center": lambda image, width, height: image.resize(
                (width, height)
            ),
            "snapshot_download": lambda **_: None,
        }

    checkpoint_dir = tmp_path / "ckpts"
    checkpoint_assets = {
        "base_model_path": str(checkpoint_dir / "stable-diffusion-inpainting"),
        "virtual_tryon_checkpoint": str(checkpoint_dir / "virtual_tryon.pth"),
    }
    monkeypatch.setattr(leffa_engine, "ensure_leffa_repo", lambda **_: None)
    monkeypatch.setattr(leffa_engine, "download_leffa_checkpoints", lambda **_: None)
    monkeypatch.setattr(leffa_engine, "load_leffa_modules", fake_load_leffa_modules)
    monkeypatch.setattr(
        leffa_engine,
        "validate_leffa_checkpoint_assets",
        lambda **_: checkpoint_assets,
    )
    monkeypatch.setattr(
        leffa_engine,
        "collect_runtime_metrics",
        lambda device: {"device": device, "peak_memory_mb": 0},
    )
    monkeypatch.setattr(leffa_engine, "validate_device_runtime", lambda device: None)

    engine = LeffaVisualEngine(
        leffa_root=tmp_path / "Leffa",
        repo_url="https://example.test/leffa.git",
        no_clone=True,
        model_repo_id="example/leffa",
        checkpoint_dir=checkpoint_dir,
        size="768x1024",
        device="cpu",
        dtype="float32",
        vt_model_type="viton_hd",
    )

    metadata = engine.load()

    assert metadata.engine == "leffa"
    assert metadata.implementation == "LeffaVisualEngine"
    assert metadata.model_repo_id == "example/leffa"
    assert metadata.checkpoint_dir == str(checkpoint_dir)
    assert metadata.device == "cpu"
    assert metadata.dtype == "float32"
    assert metadata.model_type == "viton_hd"
    assert metadata.extra["size"] == "768x1024"
    assert metadata.extra["leffa_root"] == str(tmp_path / "Leffa")
    assert metadata.extra["base_model_path"] == checkpoint_assets["base_model_path"]
    assert (
        metadata.extra["pretrained_model"]
        == checkpoint_assets["virtual_tryon_checkpoint"]
    )
    assert engine.is_ready() is True

    person_image = tmp_path / "person.png"
    garment_image = tmp_path / "garment.png"
    Image.new("RGB", (32, 48), "red").save(person_image)
    Image.new("RGB", (24, 36), "green").save(garment_image)
    output = tmp_path / "result.png"
    report = tmp_path / "result.json"

    result = engine.generate(
        GenerateRequest(
            engine="leffa",
            person_image=str(person_image),
            garment_image=str(garment_image),
            output=str(output),
            report=str(report),
            garment_type="upper_body",
            size="768x1024",
            steps=4,
            guidance_scale=2.5,
            seed=123,
            ref_acceleration=True,
            repaint=False,
            preprocess_garment=False,
        )
    )

    assert result.success is True
    assert result.engine == "leffa"
    assert result.output == str(output)
    assert result.report == str(report)
    assert Path(result.artifacts["mask_output"]).exists()
    assert Path(result.artifacts["densepose_output"]).exists()
    assert result.engine_metadata == metadata.to_dict()
    assert output.exists()
    assert report.exists()
    assert result.generation_time_seconds >= 0

    report_payload = json.loads(report.read_text("utf-8"))
    assert report_payload["success"] is True
    assert report_payload["execution_mode"] == "service"
    assert report_payload["runtime"] == {"device": "cpu", "peak_memory_mb": 0}
    assert report_payload["output"] == str(output)
    assert report_payload["mask_output"] == result.artifacts["mask_output"]
    assert report_payload["densepose_output"] == result.artifacts["densepose_output"]
    assert report_payload["request"]["seed"] == 123
    assert report_payload["engine_metadata"] == metadata.to_dict()
    assert report_payload["error"] is None
    assert load_calls == [tmp_path / "Leffa"]
