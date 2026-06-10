import json
import sys
import types
from unittest.mock import Mock

from PIL import Image

import scripts.local_qwen_edit_smoke as local_qwen_edit_smoke


def test_parse_args_supports_two_image_smoke_options(tmp_path):
    person_image = tmp_path / "person.png"
    garment_image = tmp_path / "garment.png"
    output_path = tmp_path / "out.png"

    args = local_qwen_edit_smoke.parse_args(
        [
            "--person-image",
            str(person_image),
            "--garment-image",
            str(garment_image),
            "--output",
            str(output_path),
            "--model-id",
            "Qwen/Qwen-Image-Edit-2509",
            "--pipeline",
            "edit-plus",
            "--size",
            "768x1024",
            "--device",
            "cuda",
            "--dtype",
            "bfloat16",
            "--device-map",
            "auto",
            "--cpu-offload",
            "--steps",
            "12",
            "--true-cfg-scale",
            "3.5",
            "--seed",
            "7",
        ]
    )

    assert args.person_image == person_image
    assert args.garment_image == garment_image
    assert args.output == output_path
    assert args.model_id == "Qwen/Qwen-Image-Edit-2509"
    assert args.pipeline == "edit-plus"
    assert args.size == "768x1024"
    assert args.device == "cuda"
    assert args.dtype == "bfloat16"
    assert args.device_map == "auto"
    assert args.cpu_offload is True
    assert args.steps == 12
    assert args.true_cfg_scale == 3.5
    assert args.seed == 7


def test_parse_size_rejects_invalid_size():
    try:
        local_qwen_edit_smoke.parse_size("1024")
    except ValueError as exc:
        assert "Expected size format" in str(exc)
    else:
        raise AssertionError("parse_size should reject invalid size")


def test_resolve_pipeline_name_uses_edit_plus_when_garment_exists(tmp_path):
    assert (
        local_qwen_edit_smoke.resolve_pipeline_name(
            "auto",
            garment_image=tmp_path / "garment.png",
        )
        == "edit-plus"
    )
    assert (
        local_qwen_edit_smoke.resolve_pipeline_name("auto", garment_image=None)
        == "edit"
    )


def test_generate_smoke_fails_before_loading_model_when_cuda_is_unavailable(
    tmp_path,
    monkeypatch,
):
    person_image = tmp_path / "person.png"
    output_path = tmp_path / "out.png"
    report_path = tmp_path / "report.json"
    Image.new("RGB", (16, 16), color="white").save(person_image)

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=Mock(return_value=False)),
    )
    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    load_pipeline = Mock()
    monkeypatch.setattr(local_qwen_edit_smoke, "load_pipeline", load_pipeline)

    try:
        local_qwen_edit_smoke.generate_smoke(
            person_image=person_image,
            garment_image=None,
            output=output_path,
            report=report_path,
            prompt="try on",
            negative_prompt=" ",
            model_id="Qwen/Qwen-Image-Edit-2509",
            pipeline_name="edit",
            size="16x16",
            device="cuda",
            dtype="bfloat16",
            device_map="none",
            cpu_offload=False,
            steps=2,
            true_cfg_scale=4.0,
            seed=42,
        )
    except RuntimeError as exc:
        assert "CUDA was requested" in str(exc)
    else:
        raise AssertionError("generate_smoke should fail when CUDA is unavailable")

    load_pipeline.assert_not_called()


def test_generate_smoke_fails_before_loading_model_when_torchvision_is_missing(
    tmp_path,
    monkeypatch,
):
    person_image = tmp_path / "person.png"
    output_path = tmp_path / "out.png"
    report_path = tmp_path / "report.json"
    Image.new("RGB", (16, 16), color="white").save(person_image)

    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "validate_device_runtime",
        Mock(),
    )
    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "validate_runtime_dependencies",
        Mock(side_effect=RuntimeError("torchvision is required")),
    )
    load_pipeline = Mock()
    monkeypatch.setattr(local_qwen_edit_smoke, "load_pipeline", load_pipeline)

    try:
        local_qwen_edit_smoke.generate_smoke(
            person_image=person_image,
            garment_image=None,
            output=output_path,
            report=report_path,
            prompt="try on",
            negative_prompt=" ",
            model_id="Qwen/Qwen-Image-Edit-2509",
            pipeline_name="edit",
            size="16x16",
            device="cpu",
            dtype="float32",
            device_map="none",
            cpu_offload=False,
            steps=2,
            true_cfg_scale=4.0,
            seed=42,
        )
    except RuntimeError as exc:
        assert "torchvision is required" in str(exc)
    else:
        raise AssertionError("generate_smoke should fail when torchvision is missing")

    load_pipeline.assert_not_called()


def test_generate_smoke_saves_output_and_report(tmp_path, monkeypatch):
    person_image = tmp_path / "person.png"
    garment_image = tmp_path / "garment.png"
    output_path = tmp_path / "out.png"
    report_path = tmp_path / "report.json"
    Image.new("RGB", (16, 16), color="white").save(person_image)
    Image.new("RGB", (16, 16), color="green").save(garment_image)

    pipeline = Mock()
    pipeline.return_value.images = [Image.new("RGB", (16, 16), color="blue")]

    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "load_pipeline",
        Mock(return_value=pipeline),
    )
    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "resolve_device",
        Mock(return_value="cpu"),
    )
    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "validate_runtime_dependencies",
        Mock(),
    )
    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "collect_runtime_metrics",
        Mock(return_value={"system_memory_total_gb": 10.0}),
    )

    report = local_qwen_edit_smoke.generate_smoke(
        person_image=person_image,
        garment_image=garment_image,
        output=output_path,
        report=report_path,
        prompt="try on",
        negative_prompt=" ",
        model_id="Qwen/Qwen-Image-Edit-2509",
        pipeline_name="auto",
        size="16x16",
        device="auto",
        dtype="float32",
        device_map="none",
        cpu_offload=False,
        steps=2,
        true_cfg_scale=4.0,
        seed=42,
    )

    assert output_path.exists()
    assert report_path.exists()
    assert report["success"] is True
    assert report["pipeline"] == "edit-plus"
    assert report["runtime"] == {"system_memory_total_gb": 10.0}

    saved_report = json.loads(report_path.read_text("utf-8"))
    assert saved_report["success"] is True
    assert saved_report["output"] == str(output_path)

    call_kwargs = pipeline.call_args.kwargs
    assert call_kwargs["prompt"] == "try on"
    assert call_kwargs["image"][0].size == (16, 16)
    assert call_kwargs["image"][1].size == (16, 16)
    assert call_kwargs["num_inference_steps"] == 2
    assert call_kwargs["true_cfg_scale"] == 4.0


def test_load_pipeline_cpu_offload_does_not_move_whole_pipeline_to_cuda(
    monkeypatch,
):
    class FakePipeline:
        def __init__(self):
            self.to_calls = []
            self.cpu_offload_enabled = False

        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            pipeline = cls()
            pipeline.model_id = model_id
            pipeline.from_pretrained_kwargs = kwargs
            return pipeline

        def to(self, *args):
            self.to_calls.append(args)
            return self

        def enable_model_cpu_offload(self):
            self.cpu_offload_enabled = True

        def enable_attention_slicing(self, mode):
            self.attention_slicing = mode

        def enable_vae_slicing(self):
            self.vae_slicing = True

        def set_progress_bar_config(self, **kwargs):
            self.progress_bar_kwargs = kwargs

    monkeypatch.setitem(
        sys.modules,
        "diffusers",
        types.SimpleNamespace(
            QwenImageEditPipeline=FakePipeline,
            QwenImageEditPlusPipeline=FakePipeline,
        ),
    )

    pipeline = local_qwen_edit_smoke.load_pipeline(
        model_id="Qwen/Qwen-Image-Edit-2509",
        pipeline_name="edit-plus",
        torch_dtype="bf16",
        device="cuda",
        device_map="none",
        cpu_offload=True,
    )

    assert pipeline.cpu_offload_enabled is True
    assert pipeline.to_calls == [("bf16",)]


def test_main_writes_failure_report_when_generation_fails(tmp_path, monkeypatch):
    person_image = tmp_path / "person.png"
    output_path = tmp_path / "out.png"
    report_path = tmp_path / "report.json"
    Image.new("RGB", (16, 16), color="white").save(person_image)

    monkeypatch.setattr(
        local_qwen_edit_smoke,
        "load_pipeline",
        Mock(side_effect=RuntimeError("missing qwen pipeline")),
    )

    exit_code = local_qwen_edit_smoke.main(
        [
            "--person-image",
            str(person_image),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--pipeline",
            "edit",
            "--device",
            "cpu",
            "--dtype",
            "float32",
            "--steps",
            "1",
        ]
    )

    assert exit_code == 1
    saved_report = json.loads(report_path.read_text("utf-8"))
    assert saved_report["success"] is False
    assert saved_report["error"]["type"] == "RuntimeError"
    assert "missing qwen pipeline" in saved_report["error"]["message"]
