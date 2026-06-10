import json
import sys
import types
from unittest.mock import Mock

from PIL import Image

import scripts.local_catvton_smoke as local_catvton_smoke


def test_parse_args_supports_catvton_smoke_options(tmp_path):
    person_image = tmp_path / "person.png"
    garment_image = tmp_path / "garment.png"
    output_path = tmp_path / "out.png"
    catvton_root = tmp_path / "CatVTON"
    mask_image = tmp_path / "mask.png"

    args = local_catvton_smoke.parse_args(
        [
            "--person-image",
            str(person_image),
            "--garment-image",
            str(garment_image),
            "--output",
            str(output_path),
            "--catvton-root",
            str(catvton_root),
            "--repo-url",
            "https://example.test/CatVTON.git",
            "--no-clone",
            "--base-model-path",
            "base/model",
            "--resume-path",
            "checkpoint/model",
            "--size",
            "768x1024",
            "--device",
            "cuda",
            "--mixed-precision",
            "bf16",
            "--cloth-type",
            "upper",
            "--mask-mode",
            "provided",
            "--mask-image",
            str(mask_image),
            "--steps",
            "20",
            "--guidance-scale",
            "2.0",
            "--seed",
            "7",
            "--no-allow-tf32",
            "--no-skip-safety-check",
            "--check-imports-only",
        ]
    )

    assert args.person_image == person_image
    assert args.garment_image == garment_image
    assert args.output == output_path
    assert args.catvton_root == catvton_root
    assert args.repo_url == "https://example.test/CatVTON.git"
    assert args.no_clone is True
    assert args.base_model_path == "base/model"
    assert args.resume_path == "checkpoint/model"
    assert args.size == "768x1024"
    assert args.device == "cuda"
    assert args.mixed_precision == "bf16"
    assert args.cloth_type == "upper"
    assert args.mask_mode == "provided"
    assert args.mask_image == mask_image
    assert args.steps == 20
    assert args.guidance_scale == 2.0
    assert args.seed == 7
    assert args.allow_tf32 is False
    assert args.skip_safety_check is False
    assert args.check_imports_only is True


def test_create_rough_mask_has_expected_size_and_nonzero_pixels():
    mask = local_catvton_smoke.create_rough_mask((128, 256), cloth_type="upper")

    assert mask.size == (128, 256)
    assert mask.mode == "L"
    assert max(mask.getdata()) > 0


def test_ensure_catvton_repo_uses_existing_checkout(tmp_path, monkeypatch):
    catvton_root = tmp_path / "CatVTON"
    (catvton_root / "model").mkdir(parents=True)
    (catvton_root / "model" / "pipeline.py").write_text("# test", "utf-8")
    subprocess_run = Mock()
    monkeypatch.setattr(local_catvton_smoke.subprocess, "run", subprocess_run)

    local_catvton_smoke.ensure_catvton_repo(
        catvton_root=catvton_root,
        repo_url="https://example.test/CatVTON.git",
        no_clone=False,
    )

    subprocess_run.assert_not_called()


def test_ensure_catvton_repo_clones_when_missing(tmp_path, monkeypatch):
    catvton_root = tmp_path / "CatVTON"
    subprocess_run = Mock()
    monkeypatch.setattr(local_catvton_smoke.subprocess, "run", subprocess_run)

    local_catvton_smoke.ensure_catvton_repo(
        catvton_root=catvton_root,
        repo_url="https://example.test/CatVTON.git",
        no_clone=False,
    )

    subprocess_run.assert_called_once_with(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://example.test/CatVTON.git",
            str(catvton_root),
        ],
        check=True,
    )


def test_generate_smoke_saves_output_and_report_with_fake_modules(
    tmp_path,
    monkeypatch,
):
    person_image = tmp_path / "person.png"
    garment_image = tmp_path / "garment.png"
    output_path = tmp_path / "out.png"
    report_path = tmp_path / "report.json"
    catvton_root = tmp_path / "CatVTON"
    checkpoint_root = tmp_path / "checkpoint"
    checkpoint_root.mkdir()
    Image.new("RGB", (32, 64), color="white").save(person_image)
    Image.new("RGB", (32, 64), color="green").save(garment_image)

    class FakePipeline:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs

        def __call__(self, **kwargs):
            self.call_kwargs = kwargs
            return [Image.new("RGB", (16, 16), color="blue")]

    class FakeVaeImageProcessor:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def blur(self, image, blur_factor):
            return image

    fake_pipeline = FakePipeline
    modules = {
        "AutoMasker": Mock(),
        "CatVTONPipeline": fake_pipeline,
        "VaeImageProcessor": FakeVaeImageProcessor,
        "init_weight_dtype": Mock(),
        "resize_and_crop": Mock(side_effect=lambda image, size: image.resize(size)),
        "resize_and_padding": Mock(side_effect=lambda image, size: image.resize(size)),
        "snapshot_download": Mock(return_value=str(checkpoint_root)),
    }

    monkeypatch.setattr(local_catvton_smoke, "resolve_device", Mock(return_value="cpu"))
    monkeypatch.setattr(local_catvton_smoke, "validate_device_runtime", Mock())
    monkeypatch.setattr(local_catvton_smoke, "ensure_catvton_repo", Mock())
    monkeypatch.setattr(
        local_catvton_smoke, "load_catvton_modules", Mock(return_value=modules)
    )
    monkeypatch.setattr(
        local_catvton_smoke,
        "collect_runtime_metrics",
        Mock(return_value={"system_memory_total_gb": 10.0}),
    )

    fake_torch = types.SimpleNamespace(
        float32="float32",
        float16="float16",
        bfloat16="bfloat16",
        Generator=lambda device: Mock(manual_seed=Mock(return_value="generator")),
        inference_mode=lambda: _NullContext(),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    report = local_catvton_smoke.generate_smoke(
        person_image=person_image,
        garment_image=garment_image,
        output=output_path,
        report=report_path,
        catvton_root=catvton_root,
        repo_url="https://example.test/CatVTON.git",
        no_clone=True,
        base_model_path="base/model",
        resume_path="checkpoint/model",
        size="16x16",
        device="auto",
        mixed_precision="bf16",
        cloth_type="upper",
        mask_mode="rough",
        mask_image=None,
        steps=2,
        guidance_scale=2.5,
        seed=42,
        allow_tf32=True,
        skip_safety_check=True,
    )

    assert output_path.exists()
    assert report_path.exists()
    assert report["success"] is True
    assert report["model"] == "CatVTON"
    assert report["mask_mode"] == "rough"
    assert report["runtime"] == {"system_memory_total_gb": 10.0}

    saved_report = json.loads(report_path.read_text("utf-8"))
    assert saved_report["output"] == str(output_path)
    assert saved_report["checkpoint_path"] == str(checkpoint_root)


def test_generate_smoke_import_check_does_not_require_input_files(
    tmp_path,
    monkeypatch,
):
    report_path = tmp_path / "report.json"
    catvton_root = tmp_path / "CatVTON"
    modules = {
        "CatVTONPipeline": Mock(),
        "VaeImageProcessor": Mock(),
        "init_weight_dtype": Mock(),
        "resize_and_crop": Mock(),
        "resize_and_padding": Mock(),
        "snapshot_download": Mock(),
    }

    monkeypatch.setattr(local_catvton_smoke, "resolve_device", Mock(return_value="cpu"))
    monkeypatch.setattr(local_catvton_smoke, "validate_device_runtime", Mock())
    monkeypatch.setattr(local_catvton_smoke, "ensure_catvton_repo", Mock())
    load_modules = Mock(return_value=modules)
    monkeypatch.setattr(local_catvton_smoke, "load_catvton_modules", load_modules)
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace())

    report = local_catvton_smoke.generate_smoke(
        person_image=tmp_path / "missing-person.png",
        garment_image=tmp_path / "missing-garment.png",
        output=tmp_path / "out.png",
        report=report_path,
        catvton_root=catvton_root,
        repo_url="https://example.test/CatVTON.git",
        no_clone=True,
        base_model_path="base/model",
        resume_path="checkpoint/model",
        size="16x16",
        device="auto",
        mixed_precision="bf16",
        cloth_type="upper",
        mask_mode="rough",
        mask_image=None,
        steps=2,
        guidance_scale=2.5,
        seed=42,
        allow_tf32=True,
        skip_safety_check=True,
        check_imports_only=True,
    )

    assert report["success"] is True
    assert report["check_imports_only"] is True
    assert report_path.exists()
    load_modules.assert_called_once_with(catvton_root, include_automasker=False)


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False
