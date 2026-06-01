import base64
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.modules.evaluation.harness import (
    EvalCase,
    EvalRunner,
    PreviewModelConfig,
    file_sha256,
    load_eval_cases,
    load_preview_model_configs,
)
from src.modules.evaluation.output_safety import (
    PreviewOutputSafetyPostprocessor,
    PreviewPostprocessResult,
)
from src.schemas.responses import ClothingAnalysis


def test_file_sha256_returns_stable_digest(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"image-bytes")

    assert file_sha256(image_path) == (
        "2c8648d103e3dd7ad87660da0f126a1443b6d21ac1bd3ec000c5e24e2373a90c"
    )


def test_load_eval_cases_resolves_paths_relative_to_manifest(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "upper-body-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {
                            "garment_preservation": "",
                            "pose_preservation": "",
                            "face_privacy": "",
                            "background_stability": "",
                            "overall": "",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_eval_cases(manifest_path)

    assert cases == [
        EvalCase(
            case_id="upper-body-001",
            anonymized_user_image_path=user_path,
            product_image_path=product_path,
            mask_path=None,
            manual_quality_notes={
                "garment_preservation": "",
                "pose_preservation": "",
                "face_privacy": "",
                "background_stability": "",
                "overall": "",
            },
        )
    ]


def test_eval_runner_writes_success_report(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Blue jersey",
        body_pose="Standing upright",
        inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
        confidence_score=0.91,
        additional_notes="",
    )

    image_generator = Mock()
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    image_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"generated-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
    )

    result = runner.run_cases(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={
                    "garment_preservation": "",
                    "pose_preservation": "",
                    "face_privacy": "",
                    "background_stability": "",
                    "overall": "",
                },
            )
        ],
        report_path=report_path,
    )

    assert result["summary"]["total_cases"] == 1
    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 0
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    case_result = payload["cases"][0]
    assert case_result["case_id"] == "upper-body-001"
    assert case_result["status"] == "succeeded"
    assert case_result["semantic"]["provider"] == "ollama"
    assert case_result["semantic"]["model"] == "vto-brain"
    assert case_result["semantic"]["prompt_version"] == "semantic-edit-safe-v1"
    assert case_result["preview"]["model"] == "qwen/qwen-image-edit-2511"
    assert case_result["preview"]["prompt_version"] == "preview-garment-swap-v1"
    generated_path = Path(case_result["preview"]["generated_image_path"])
    assert generated_path.exists()
    assert generated_path.read_bytes() == b"generated-image"
    assert case_result["input_hashes"]["user_image_sha256"] == file_sha256(user_path)
    assert case_result["input_hashes"]["product_image_sha256"] == file_sha256(
        product_path
    )
    assert case_result["manual_quality_notes"]["overall"] == ""


def test_eval_runner_records_failed_case_and_continues(tmp_path):
    first_user_path = tmp_path / "first-user.png"
    first_product_path = tmp_path / "first-product.png"
    second_user_path = tmp_path / "second-user.png"
    second_product_path = tmp_path / "second-product.png"
    report_path = tmp_path / "report.json"
    for path in [
        first_user_path,
        first_product_path,
        second_user_path,
        second_product_path,
    ]:
        path.write_bytes(path.name.encode("utf-8"))

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.side_effect = [
        RuntimeError("ollama unavailable"),
        ClothingAnalysis(
            clothing_description="Black hoodie",
            body_pose="Front-facing",
            inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
            confidence_score=0.88,
            additional_notes="",
        ),
    ]

    image_generator = Mock()
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    image_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"generated-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
    )

    result = runner.run_cases(
        cases=[
            EvalCase(
                case_id="case-fails",
                anonymized_user_image_path=first_user_path,
                product_image_path=first_product_path,
                mask_path=None,
                manual_quality_notes={},
            ),
            EvalCase(
                case_id="case-succeeds",
                anonymized_user_image_path=second_user_path,
                product_image_path=second_product_path,
                mask_path=None,
                manual_quality_notes={},
            ),
        ],
        report_path=report_path,
    )

    assert result["summary"]["total_cases"] == 2
    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["status"] == "failed"
    assert payload["cases"][0]["error"] == "ollama unavailable"
    assert payload["cases"][1]["status"] == "succeeded"


def test_eval_runner_writes_multi_preview_report_grouped_by_case(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Blue jersey",
        body_pose="Standing upright",
        inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
        confidence_score=0.91,
        additional_notes="",
    )

    first_generator = Mock()
    first_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    first_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"qwen-image"
    ).decode("utf-8")

    second_generator = Mock()
    second_generator.get_runtime_metadata.return_value = {
        "preview_model": "google/nano-banana",
        "preview_input_mapping": "google_nano_banana",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    second_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"nano-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=first_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={"overall": ""},
            )
        ],
        preview_generators=[
            ("qwen_current", first_generator),
            ("nano_banana_current", second_generator),
        ],
        report_path=report_path,
    )

    assert semantic_parser.analyze_vto_context.call_count == 1
    assert result["summary"] == {
        "total_cases": 1,
        "preview_runs_per_case": 2,
        "total_preview_runs": 2,
        "succeeded": 2,
        "failed": 0,
    }
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    case_result = payload["cases"][0]
    assert case_result["case_id"] == "upper-body-001"
    assert len(case_result["preview_results"]) == 2
    assert case_result["preview_results"][0]["run_id"] == "qwen_current"
    assert case_result["preview_results"][0]["model"] == "qwen/qwen-image-edit-2511"
    assert case_result["preview_results"][1]["run_id"] == "nano_banana_current"
    assert case_result["preview_results"][1]["model"] == "google/nano-banana"
    assert (
        Path(case_result["preview_results"][0]["generated_image_path"]).read_bytes()
        == b"qwen-image"
    )
    assert (
        Path(case_result["preview_results"][1]["generated_image_path"]).read_bytes()
        == b"nano-image"
    )


def test_eval_runner_applies_preview_postprocessor_to_multi_preview_outputs(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    mask_path = tmp_path / "mask.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    mask_path.write_bytes(b"mask-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Blue jersey",
        body_pose="Standing upright",
        inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
        confidence_score=0.91,
        additional_notes="",
    )

    image_generator = Mock()
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    image_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"raw-image"
    ).decode("utf-8")

    postprocessor = Mock(
        return_value=PreviewPostprocessResult(
            image_b64=base64.b64encode(b"safe-image").decode("utf-8"),
            mask_applied=True,
            mask_source="manifest",
            face_preserve_applied=True,
            face_preserve_source="anonymized base image",
        )
    )
    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
        preview_postprocessor=postprocessor,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=mask_path,
                manual_quality_notes={"overall": ""},
            )
        ],
        preview_generators=[("qwen_current", image_generator)],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 1
    postprocessor.assert_called_once_with(
        base_image_b64=base64.b64encode(b"user-image").decode("utf-8"),
        generated_image_b64=base64.b64encode(b"raw-image").decode("utf-8"),
        mask_b64=base64.b64encode(b"mask-image").decode("utf-8"),
        preview_metadata={
            "model": "qwen/qwen-image-edit-2511",
            "input_mapping": "multi_image_edit",
            "prompt_version": "preview-garment-swap-v1",
        },
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    preview_result = payload["cases"][0]["preview_results"][0]
    assert Path(preview_result["generated_image_path"]).read_bytes() == b"safe-image"
    assert preview_result["postprocessing"] == {
        "mask_applied": True,
        "mask_source": "manifest",
        "face_preserve_applied": True,
        "face_preserve_source": "anonymized base image",
    }


def test_eval_runner_uses_clothing_description_for_idm_vton_garment_description(
    tmp_path,
):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Mint green short sleeve jersey with navy trim",
        body_pose="Standing with arms crossed",
        inpainting_prompt="Edit only the first image and preserve the body pose.",
        confidence_score=0.91,
        additional_notes="",
    )

    image_generator = Mock()
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "0513734",
        "preview_input_mapping": "replicate_idm_vton",
        "preview_prompt_version": "idm-vton-v1",
    }
    image_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"idm-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={},
            )
        ],
        preview_generators=[("idm_vton_upper_body", image_generator)],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 1
    image_generator.generate_tryon_from_b64.assert_called_once()
    assert (
        image_generator.generate_tryon_from_b64.call_args.kwargs["inpainting_prompt"]
        == "Mint green short sleeve jersey with navy trim"
    )


def test_eval_runner_skips_semantic_analysis_for_promptless_oot_diffusion(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.side_effect = RuntimeError(
        "semantic should be skipped"
    )

    image_generator = Mock()
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "9f8fa495",
        "preview_input_mapping": "replicate_oot_diffusion",
        "preview_prompt_version": "oot-diffusion-v1",
    }
    image_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"oot-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-002",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={},
            )
        ],
        preview_generators=[("oot_diffusion_upper_body", image_generator)],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 1
    semantic_parser.analyze_vto_context.assert_not_called()
    image_generator.generate_tryon_from_b64.assert_called_once()
    assert (
        image_generator.generate_tryon_from_b64.call_args.kwargs["inpainting_prompt"]
        == ""
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["semantic"] == {
        "provider": "skipped",
        "model": "not-required",
        "prompt_version": "not-required",
        "latency_seconds": 0.0,
        "confidence_score": 0.0,
        "clothing_description": "",
        "body_pose": "",
        "additional_notes": "Semantic analysis skipped for promptless preview generator.",
    }


def test_eval_runner_records_failed_preview_run_and_continues(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Black hoodie",
        body_pose="Front-facing",
        inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
        confidence_score=0.88,
        additional_notes="",
    )

    failing_generator = Mock()
    failing_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    failing_generator.generate_tryon_from_b64.side_effect = RuntimeError(
        "replicate unavailable"
    )

    succeeding_generator = Mock()
    succeeding_generator.get_runtime_metadata.return_value = {
        "preview_model": "google/nano-banana",
        "preview_input_mapping": "google_nano_banana",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    succeeding_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"nano-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=failing_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={},
            )
        ],
        preview_generators=[
            ("qwen_current", failing_generator),
            ("nano_banana_current", succeeding_generator),
        ],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["status"] == "failed"
    assert payload["cases"][0]["error"] == "One or more preview runs failed"
    preview_results = payload["cases"][0]["preview_results"]
    assert preview_results[0]["status"] == "failed"
    assert preview_results[0]["error"] == "replicate unavailable"
    assert preview_results[1]["status"] == "succeeded"


def test_eval_runner_records_failed_preview_metadata_and_continues(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Black hoodie",
        body_pose="Front-facing",
        inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
        confidence_score=0.88,
        additional_notes="",
    )

    failing_generator = Mock()
    failing_generator.get_runtime_metadata.side_effect = RuntimeError(
        "metadata unavailable"
    )

    succeeding_generator = Mock()
    succeeding_generator.get_runtime_metadata.return_value = {
        "preview_model": "google/nano-banana",
        "preview_input_mapping": "google_nano_banana",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    succeeding_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"nano-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=failing_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={},
            )
        ],
        preview_generators=[
            ("qwen_current", failing_generator),
            ("nano_banana_current", succeeding_generator),
        ],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["status"] == "failed"
    assert payload["cases"][0]["error"] == "One or more preview runs failed"
    preview_results = payload["cases"][0]["preview_results"]
    assert preview_results[0]["status"] == "failed"
    assert preview_results[0]["error"] == "metadata unavailable"
    assert preview_results[0]["model"] is None
    assert preview_results[0]["input_mapping"] is None
    assert preview_results[0]["prompt_version"] is None
    assert preview_results[0]["generated_image_bytes"] is None
    assert preview_results[0]["generated_image_path"] is None
    assert preview_results[1]["status"] == "succeeded"


def test_eval_runner_records_malformed_preview_metadata_and_continues(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.return_value = ClothingAnalysis(
        clothing_description="Black hoodie",
        body_pose="Front-facing",
        inpainting_prompt="Use IMAGE 1 as base and IMAGE 2 as garment reference.",
        confidence_score=0.88,
        additional_notes="",
    )

    malformed_generator = Mock()
    malformed_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
    }
    malformed_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"qwen-image"
    ).decode("utf-8")

    succeeding_generator = Mock()
    succeeding_generator.get_runtime_metadata.return_value = {
        "preview_model": "google/nano-banana",
        "preview_input_mapping": "google_nano_banana",
        "preview_prompt_version": "preview-garment-swap-v1",
    }
    succeeding_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        b"nano-image"
    ).decode("utf-8")

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=malformed_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={},
            )
        ],
        preview_generators=[
            ("qwen_current", malformed_generator),
            ("nano_banana_current", succeeding_generator),
        ],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["failed"] == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["status"] == "failed"
    assert payload["cases"][0]["error"] == "One or more preview runs failed"
    preview_results = payload["cases"][0]["preview_results"]
    assert preview_results[0]["status"] == "failed"
    assert "preview_prompt_version" in preview_results[0]["error"]
    assert preview_results[0]["model"] == "qwen/qwen-image-edit-2511"
    assert preview_results[0]["input_mapping"] == "multi_image_edit"
    assert preview_results[0]["prompt_version"] is None
    assert preview_results[1]["status"] == "succeeded"


def test_eval_runner_counts_semantic_failure_in_multi_preview_summary(tmp_path):
    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    report_path = tmp_path / "report.json"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")

    semantic_parser = Mock()
    semantic_parser.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "vto-brain",
        "semantic_prompt_version": "semantic-edit-safe-v1",
    }
    semantic_parser.analyze_vto_context.side_effect = RuntimeError(
        "semantic unavailable"
    )

    image_generator = Mock()
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "qwen/qwen-image-edit-2511",
        "preview_input_mapping": "multi_image_edit",
        "preview_prompt_version": "preview-garment-swap-v1",
    }

    runner = EvalRunner(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
    )

    result = runner.run_cases_with_preview_generators(
        cases=[
            EvalCase(
                case_id="upper-body-001",
                anonymized_user_image_path=user_path,
                product_image_path=product_path,
                mask_path=None,
                manual_quality_notes={},
            )
        ],
        preview_generators=[("qwen_current", image_generator)],
        report_path=report_path,
    )

    assert result["summary"]["succeeded"] == 0
    assert result["summary"]["failed"] == 1
    assert result["summary"]["total_preview_runs"] == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    case_result = payload["cases"][0]
    assert case_result["status"] == "failed"
    assert case_result["error"] == "semantic unavailable"
    assert case_result["preview_results"] == []


def test_eval_runner_rejects_empty_preview_generators(tmp_path):
    runner = EvalRunner(
        semantic_parser=Mock(),
        image_generator=Mock(),
    )
    report_path = tmp_path / "report.json"

    with pytest.raises(ValueError, match="At least one preview generator is required"):
        runner.run_cases_with_preview_generators(
            cases=[],
            preview_generators=[],
            report_path=report_path,
        )

    assert not report_path.exists()


def test_run_vto_eval_parse_args_defaults(tmp_path):
    from scripts.run_vto_eval import parse_args

    manifest_path = tmp_path / "manifest.json"
    args = parse_args(["--manifest", str(manifest_path)])

    assert args.manifest == manifest_path
    assert args.report_path is None
    assert args.model_matrix is None
    assert args.limit_cases is None
    assert args.dry_run is False
    assert args.apply_mask_postprocess is False


def test_run_vto_eval_parse_args_supports_cost_controls(tmp_path):
    from scripts.run_vto_eval import parse_args

    manifest_path = tmp_path / "manifest.json"
    matrix_path = tmp_path / "model_matrix.json"
    report_path = tmp_path / "report.json"

    args = parse_args(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--report-path",
            str(report_path),
            "--limit-cases",
            "2",
            "--dry-run",
            "--apply-mask-postprocess",
        ]
    )

    assert args.manifest == manifest_path
    assert args.model_matrix == matrix_path
    assert args.report_path == report_path
    assert args.limit_cases == 2
    assert args.dry_run is True
    assert args.apply_mask_postprocess is True


@pytest.mark.parametrize("limit_cases", ["0", "-1"])
def test_run_vto_eval_parse_args_rejects_non_positive_limit_cases(
    tmp_path,
    limit_cases,
):
    from scripts.run_vto_eval import parse_args

    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(SystemExit):
        parse_args(
            [
                "--manifest",
                str(manifest_path),
                "--limit-cases",
                limit_cases,
            ]
        )


def test_build_dry_run_plan_does_not_call_providers(tmp_path):
    from scripts.run_vto_eval import build_dry_run_plan

    cases = [
        EvalCase(
            case_id="case-001",
            anonymized_user_image_path=tmp_path / "user.png",
            product_image_path=tmp_path / "product.png",
            mask_path=None,
            manual_quality_notes={},
        )
    ]
    configs = [
        PreviewModelConfig(
            run_id="qwen_current",
            model="qwen/qwen-image-edit-2511",
            model_version=None,
            input_mapping="multi_image_edit",
            prompt_variant="preview-garment-swap-v1",
        )
    ]

    plan = build_dry_run_plan(cases=cases, preview_model_configs=configs)

    assert plan == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "qwen_current",
                "model": "qwen/qwen-image-edit-2511",
                "input_mapping": "multi_image_edit",
                "prompt_variant": "preview-garment-swap-v1",
            }
        ],
    }


def test_build_preview_generator_from_config_sets_eval_fields():
    from scripts.run_vto_eval import build_preview_generator_from_config

    config = PreviewModelConfig(
        run_id="nano_banana_current",
        model="google/nano-banana",
        model_version=None,
        input_mapping="google_nano_banana",
        prompt_variant="preview-garment-preserve-v2",
    )
    generator = Mock()
    generator_factory = Mock(return_value=generator)

    result = build_preview_generator_from_config(
        config,
        generator_factory=generator_factory,
    )

    assert result is generator
    generator_factory.assert_called_once_with()
    assert result.model == "google/nano-banana"
    assert result.model_version is None
    assert result.input_mapping == "google_nano_banana"
    assert result.prompt_variant == "preview-garment-preserve-v2"


def test_build_preview_generator_from_config_supports_replicate_idm_vton():
    from scripts.run_vto_eval import build_preview_generator_from_config
    from src.modules.image_generator.replicate_idm_vton_generator import (
        ReplicateIdmVtonGenerator,
    )

    config = PreviewModelConfig(
        run_id="idm_vton_upper_body",
        model="cuuupid/idm-vton",
        model_version="0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
        input_mapping="replicate_idm_vton",
        prompt_variant="idm-vton-v1",
    )

    generator = build_preview_generator_from_config(config)

    assert isinstance(generator, ReplicateIdmVtonGenerator)
    assert generator.model == "cuuupid/idm-vton"
    assert generator.model_version == (
        "0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985"
    )
    assert generator.input_mapping == "replicate_idm_vton"
    assert generator.prompt_variant == "idm-vton-v1"


def test_build_preview_generator_from_config_supports_replicate_flux_vton():
    from scripts.run_vto_eval import build_preview_generator_from_config
    from src.modules.image_generator.replicate_flux_vton_generator import (
        ReplicateFluxVtonGenerator,
    )

    config = PreviewModelConfig(
        run_id="flux_vton_upper_body",
        model="subhash25rawat/flux-vton",
        model_version="a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199",
        input_mapping="replicate_flux_vton",
        prompt_variant="flux-vton-v1",
    )

    generator = build_preview_generator_from_config(config)

    assert isinstance(generator, ReplicateFluxVtonGenerator)
    assert generator.model == "subhash25rawat/flux-vton"
    assert generator.model_version == (
        "a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199"
    )
    assert generator.input_mapping == "replicate_flux_vton"
    assert generator.prompt_variant == "flux-vton-v1"


def test_build_preview_generator_from_config_supports_flux_kontext():
    from scripts.run_vto_eval import build_preview_generator_from_config
    from src.modules.image_generator.replicate_flux_kontext_generator import (
        ReplicateFluxKontextGenerator,
    )

    config = PreviewModelConfig(
        run_id="flux_kontext_outfit_preview",
        model="flux-kontext-apps/multi-image-kontext-pro",
        model_version=None,
        input_mapping="flux_kontext_multi_image",
        prompt_variant="flux-kontext-outfit-preview-v1",
    )

    generator = build_preview_generator_from_config(config)

    assert isinstance(generator, ReplicateFluxKontextGenerator)
    assert generator.model == "flux-kontext-apps/multi-image-kontext-pro"
    assert generator.model_version is None
    assert generator.input_mapping == "flux_kontext_multi_image"
    assert generator.prompt_variant == "flux-kontext-outfit-preview-v1"


def test_build_preview_generator_from_config_supports_oot_diffusion():
    from scripts.run_vto_eval import build_preview_generator_from_config
    from src.modules.image_generator.replicate_oot_diffusion_generator import (
        ReplicateOotDiffusionGenerator,
    )

    config = PreviewModelConfig(
        run_id="oot_diffusion_upper_body",
        model="viktorfa/oot_diffusion",
        model_version="9f8fa4956970dde99689af7488157a30aa152e23953526a605df1d77598343d7",
        input_mapping="replicate_oot_diffusion",
        prompt_variant="oot-diffusion-v1",
    )

    generator = build_preview_generator_from_config(config)

    assert isinstance(generator, ReplicateOotDiffusionGenerator)
    assert generator.model == "viktorfa/oot_diffusion"
    assert generator.model_version == (
        "9f8fa4956970dde99689af7488157a30aa152e23953526a605df1d77598343d7"
    )
    assert generator.input_mapping == "replicate_oot_diffusion"
    assert generator.prompt_variant == "oot-diffusion-v1"


def test_run_vto_eval_main_model_matrix_dry_run_does_not_instantiate_providers(
    tmp_path,
    monkeypatch,
    capsys,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    assert return_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "qwen_current",
                "model": "qwen/qwen-image-edit-2511",
                "input_mapping": "multi_image_edit",
                "prompt_variant": "preview-garment-swap-v1",
            }
        ],
    }
    semantic_client.assert_not_called()
    preview_generator.assert_not_called()


def test_run_vto_eval_main_model_matrix_dry_run_accepts_idm_vton(
    tmp_path,
    monkeypatch,
    capsys,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "idm_vton_upper_body",
                        "model": "cuuupid/idm-vton",
                        "model_version": "0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
                        "input_mapping": "replicate_idm_vton",
                        "prompt_variant": "idm-vton-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    idm_generator = Mock(side_effect=AssertionError("idm generator instantiated"))
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(run_vto_eval, "ReplicateIdmVtonGenerator", idm_generator)

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    assert return_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "idm_vton_upper_body",
                "model": "cuuupid/idm-vton",
                "input_mapping": "replicate_idm_vton",
                "prompt_variant": "idm-vton-v1",
            }
        ],
    }
    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    idm_generator.assert_not_called()


def test_run_vto_eval_main_model_matrix_dry_run_accepts_flux_vton(
    tmp_path,
    monkeypatch,
    capsys,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "flux_vton_upper_body",
                        "model": "subhash25rawat/flux-vton",
                        "model_version": "a02643ce418c0e12bad371c4adbfaec0dd1cb34b034ef37650ef205f92ad6199",
                        "input_mapping": "replicate_flux_vton",
                        "prompt_variant": "flux-vton-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    idm_generator = Mock(side_effect=AssertionError("idm generator instantiated"))
    flux_generator = Mock(side_effect=AssertionError("flux generator instantiated"))
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(run_vto_eval, "ReplicateIdmVtonGenerator", idm_generator)
    monkeypatch.setattr(run_vto_eval, "ReplicateFluxVtonGenerator", flux_generator)

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    assert return_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "flux_vton_upper_body",
                "model": "subhash25rawat/flux-vton",
                "input_mapping": "replicate_flux_vton",
                "prompt_variant": "flux-vton-v1",
            }
        ],
    }
    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    idm_generator.assert_not_called()
    flux_generator.assert_not_called()


def test_run_vto_eval_main_model_matrix_dry_run_accepts_flux_kontext(
    tmp_path,
    monkeypatch,
    capsys,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "flux_kontext_outfit_preview",
                        "model": "flux-kontext-apps/multi-image-kontext-pro",
                        "model_version": None,
                        "input_mapping": "flux_kontext_multi_image",
                        "prompt_variant": "flux-kontext-outfit-preview-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    idm_generator = Mock(side_effect=AssertionError("idm generator instantiated"))
    flux_vton_generator = Mock(
        side_effect=AssertionError("flux vton generator instantiated")
    )
    flux_kontext_generator = Mock(
        side_effect=AssertionError("flux kontext generator instantiated")
    )
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(run_vto_eval, "ReplicateIdmVtonGenerator", idm_generator)
    monkeypatch.setattr(
        run_vto_eval,
        "ReplicateFluxVtonGenerator",
        flux_vton_generator,
    )
    monkeypatch.setattr(
        run_vto_eval,
        "ReplicateFluxKontextGenerator",
        flux_kontext_generator,
    )

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    assert return_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "flux_kontext_outfit_preview",
                "model": "flux-kontext-apps/multi-image-kontext-pro",
                "input_mapping": "flux_kontext_multi_image",
                "prompt_variant": "flux-kontext-outfit-preview-v1",
            }
        ],
    }
    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    idm_generator.assert_not_called()
    flux_vton_generator.assert_not_called()
    flux_kontext_generator.assert_not_called()


def test_run_vto_eval_main_model_matrix_dry_run_accepts_oot_diffusion(
    tmp_path,
    monkeypatch,
    capsys,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "oot_diffusion_upper_body",
                        "model": "viktorfa/oot_diffusion",
                        "model_version": "9f8fa4956970dde99689af7488157a30aa152e23953526a605df1d77598343d7",
                        "input_mapping": "replicate_oot_diffusion",
                        "prompt_variant": "oot-diffusion-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    idm_generator = Mock(side_effect=AssertionError("idm generator instantiated"))
    flux_vton_generator = Mock(
        side_effect=AssertionError("flux vton generator instantiated")
    )
    flux_kontext_generator = Mock(
        side_effect=AssertionError("flux kontext generator instantiated")
    )
    oot_diffusion_generator = Mock(
        side_effect=AssertionError("oot diffusion generator instantiated")
    )
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(run_vto_eval, "ReplicateIdmVtonGenerator", idm_generator)
    monkeypatch.setattr(
        run_vto_eval,
        "ReplicateFluxVtonGenerator",
        flux_vton_generator,
    )
    monkeypatch.setattr(
        run_vto_eval,
        "ReplicateFluxKontextGenerator",
        flux_kontext_generator,
    )
    monkeypatch.setattr(
        run_vto_eval,
        "ReplicateOotDiffusionGenerator",
        oot_diffusion_generator,
    )

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    assert return_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "oot_diffusion_upper_body",
                "model": "viktorfa/oot_diffusion",
                "input_mapping": "replicate_oot_diffusion",
                "prompt_variant": "oot-diffusion-v1",
            }
        ],
    }
    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    idm_generator.assert_not_called()
    flux_vton_generator.assert_not_called()
    flux_kontext_generator.assert_not_called()
    oot_diffusion_generator.assert_not_called()


@pytest.mark.parametrize("dry_run_args", [[], ["--dry-run"]])
def test_run_vto_eval_main_model_matrix_rejects_no_enabled_preview_configs(
    tmp_path,
    monkeypatch,
    dry_run_args,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_disabled",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    generator_factory = Mock(side_effect=AssertionError("factory called"))
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(
        run_vto_eval,
        "build_preview_generator_from_config",
        generator_factory,
    )

    with pytest.raises(ValueError, match="No enabled preview model configs"):
        run_vto_eval.main(
            [
                "--manifest",
                str(manifest_path),
                "--model-matrix",
                str(matrix_path),
                "--report-path",
                str(tmp_path / "report.json"),
                *dry_run_args,
            ]
        )

    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    generator_factory.assert_not_called()


@pytest.mark.parametrize(
    ("field_name", "field_value", "error_match"),
    [
        (
            "input_mapping",
            "missing_mapping",
            "Unsupported preview input_mapping",
        ),
        (
            "prompt_variant",
            "missing-variant",
            "Unsupported preview prompt_variant",
        ),
    ],
)
@pytest.mark.parametrize("dry_run_args", [[], ["--dry-run"]])
def test_run_vto_eval_main_model_matrix_rejects_unsupported_enabled_configs(
    tmp_path,
    monkeypatch,
    field_name,
    field_value,
    error_match,
    dry_run_args,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    preview_config = {
        "run_id": "unsupported",
        "model": "example/unsupported",
        "model_version": None,
        "input_mapping": "multi_image_edit",
        "prompt_variant": "preview-garment-swap-v1",
        "enabled": True,
    }
    preview_config[field_name] = field_value
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps({"preview_models": [preview_config]}),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    generator_factory = Mock(side_effect=AssertionError("factory called"))
    settings_loader = Mock(side_effect=AssertionError("settings loaded"))
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(
        run_vto_eval,
        "build_preview_generator_from_config",
        generator_factory,
    )
    monkeypatch.setattr(run_vto_eval, "get_settings", settings_loader)

    with pytest.raises(ValueError, match=error_match):
        run_vto_eval.main(
            [
                "--manifest",
                str(manifest_path),
                "--model-matrix",
                str(matrix_path),
                "--report-path",
                str(tmp_path / "report.json"),
                *dry_run_args,
            ]
        )

    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    generator_factory.assert_not_called()
    settings_loader.assert_not_called()


def test_run_vto_eval_main_default_dry_run_does_not_instantiate_providers_or_settings(
    tmp_path,
    monkeypatch,
    capsys,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    semantic_client = Mock(side_effect=AssertionError("semantic client instantiated"))
    preview_generator = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    settings_loader = Mock(side_effect=AssertionError("settings loaded"))
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(run_vto_eval, "get_settings", settings_loader)

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--dry-run",
        ]
    )

    assert return_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
        },
        "planned_runs": [
            {
                "case_id": "case-001",
                "run_id": "default",
                "model": "settings.REPLICATE_PREVIEW_MODEL",
                "input_mapping": "settings.REPLICATE_PREVIEW_INPUT_MAPPING",
                "prompt_variant": "preview-garment-swap-v1",
            }
        ],
    }
    semantic_client.assert_not_called()
    preview_generator.assert_not_called()
    settings_loader.assert_not_called()


def test_run_vto_eval_main_model_matrix_actual_enables_output_safety(
    tmp_path,
    monkeypatch,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"
    semantic_parser = object()
    image_generator = object()
    semantic_client = Mock(return_value=semantic_parser)
    generator_builder = Mock(return_value=image_generator)
    runner = Mock()
    runner.run_cases_with_preview_generators.return_value = {
        "summary": {
            "total_cases": 1,
            "preview_runs_per_case": 1,
            "total_preview_runs": 1,
            "succeeded": 1,
            "failed": 0,
        }
    }
    runner_class = Mock(return_value=runner)
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(
        run_vto_eval,
        "build_preview_generator_from_config",
        generator_builder,
    )
    monkeypatch.setattr(run_vto_eval, "EvalRunner", runner_class)

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--report-path",
            str(report_path),
        ]
    )

    assert return_code == 0
    runner_class.assert_called_once()
    kwargs = runner_class.call_args.kwargs
    assert kwargs["semantic_parser"] is semantic_parser
    assert kwargs["image_generator"] is image_generator
    generator_builder.assert_called_once()
    assert isinstance(
        kwargs["preview_postprocessor"],
        PreviewOutputSafetyPostprocessor,
    )
    assert kwargs["preview_postprocessor"].apply_mask is False
    runner.run_cases_with_preview_generators.assert_called_once()
    assert runner.run_cases_with_preview_generators.call_args.kwargs[
        "preview_generators"
    ] == [("qwen_current", image_generator)]


@pytest.mark.parametrize(
    ("failed", "expected_return_code"),
    [
        (0, 0),
        (1, 1),
    ],
)
def test_run_vto_eval_main_default_actual_return_code_matches_summary(
    tmp_path,
    monkeypatch,
    capsys,
    failed,
    expected_return_code,
):
    import scripts.run_vto_eval as run_vto_eval

    user_path = tmp_path / "user.png"
    product_path = tmp_path / "product.png"
    user_path.write_bytes(b"user-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "anonymized_user_image_path": "user.png",
                        "product_image_path": "product.png",
                        "mask_path": None,
                        "manual_quality_notes": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"
    semantic_parser = object()
    image_generator = object()
    semantic_client = Mock(return_value=semantic_parser)
    preview_generator = Mock(return_value=image_generator)
    runner = Mock()
    runner.run_cases.return_value = {
        "summary": {
            "total_cases": 1,
            "succeeded": 1 - failed,
            "failed": failed,
        }
    }
    runner_class = Mock(return_value=runner)
    monkeypatch.setattr(run_vto_eval, "SemanticParserClient", semantic_client)
    monkeypatch.setattr(run_vto_eval, "ReplicatePreviewGenerator", preview_generator)
    monkeypatch.setattr(run_vto_eval, "EvalRunner", runner_class)

    return_code = run_vto_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--report-path",
            str(report_path),
        ]
    )

    assert return_code == expected_return_code
    semantic_client.assert_called_once_with()
    preview_generator.assert_called_once_with()
    runner_class.assert_called_once_with(
        semantic_parser=semantic_parser,
        image_generator=image_generator,
    )
    runner.run_cases.assert_called_once()
    assert runner.run_cases.call_args.kwargs["report_path"] == report_path
    output = capsys.readouterr().out
    summary_json = output.split("\nReport written to ", 1)[0]
    assert json.loads(summary_json) == {
        "failed": failed,
        "succeeded": 1 - failed,
        "total_cases": 1,
    }


def test_load_preview_model_configs_filters_disabled_entries(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    },
                    {
                        "run_id": "flux_disabled",
                        "model": "flux-kontext-apps/multi-image-kontext-pro",
                        "model_version": None,
                        "input_mapping": "flux_kontext_multi_image",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    configs = load_preview_model_configs(matrix_path)

    assert configs == [
        PreviewModelConfig(
            run_id="qwen_current",
            model="qwen/qwen-image-edit-2511",
            model_version=None,
            input_mapping="multi_image_edit",
            prompt_variant="preview-garment-swap-v1",
        )
    ]


def test_load_preview_model_configs_rejects_duplicate_run_ids(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "duplicate",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    },
                    {
                        "run_id": "duplicate",
                        "model": "google/nano-banana",
                        "model_version": None,
                        "input_mapping": "google_nano_banana",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate preview run_id"):
        load_preview_model_configs(matrix_path)


def test_load_preview_model_configs_defaults_omitted_prompt_variant(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    configs = load_preview_model_configs(matrix_path)

    assert configs[0].prompt_variant == "preview-garment-swap-v1"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"preview_models": None},
        {"preview_models": {}},
        {"preview_models": "qwen"},
    ],
)
def test_load_preview_model_configs_requires_preview_models_list(tmp_path, payload):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="preview_models must be a list"):
        load_preview_model_configs(matrix_path)


def test_load_preview_model_configs_rejects_missing_required_field(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"preview_models\[0\]\.model"):
        load_preview_model_configs(matrix_path)


def test_load_preview_model_configs_rejects_null_prompt_variant(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": None,
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"preview_models\[0\]\.prompt_variant"):
        load_preview_model_configs(matrix_path)


def test_load_preview_model_configs_rejects_non_boolean_enabled(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": "false",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"preview_models\[0\]\.enabled must be a boolean",
    ):
        load_preview_model_configs(matrix_path)


def test_load_preview_model_configs_rejects_whitespace_required_string(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "   ",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"preview_models\[0\]\.run_id"):
        load_preview_model_configs(matrix_path)


def test_load_preview_model_configs_rejects_whitespace_model_version(tmp_path):
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen_current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": "   ",
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "preview-garment-swap-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"preview_models\[0\]\.model_version"):
        load_preview_model_configs(matrix_path)


def test_eval_example_model_matrix_loads():
    configs = load_preview_model_configs(Path("docs/eval/model_matrix.example.json"))

    assert [config.run_id for config in configs] == ["qwen_current"]
    assert configs[0].prompt_variant == "preview-garment-swap-v1"
    assert configs[0].input_mapping == "multi_image_edit"


def test_eval_real_manifest_example_loads_paths():
    cases = load_eval_cases(Path("docs/eval/real_manifest.example.json"))

    assert len(cases) == 3
    assert cases[0].case_id == "upper-body-001"
    assert str(cases[0].anonymized_user_image_path).endswith(
        "data/eval/upper-body-001-user.png"
    )
