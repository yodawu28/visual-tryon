import base64
import json
from pathlib import Path
from unittest.mock import Mock

from src.modules.evaluation.avatar_harness import (
    AvatarEvalRunner,
    build_avatar_dry_run_plan,
    load_avatar_eval_cases,
)
from src.modules.evaluation.harness import PreviewModelConfig, file_sha256


def _write_avatar_manifest(tmp_path: Path) -> Path:
    avatar_path = tmp_path / "avatar.png"
    product_path = tmp_path / "product.png"
    avatar_path.write_bytes(b"avatar-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "avatar-upper-001",
                        "avatar_image_path": "avatar.png",
                        "product_image_path": "product.png",
                        "body_profile": {
                            "input_mode": "detailed",
                            "detailed": {
                                "gender_presentation": "male",
                                "height_cm": 182,
                                "weight_kg": 84,
                                "shoulder_width_cm": 49,
                                "chest_or_bust_cm": 104,
                                "waist_cm": 86,
                                "hip_cm": 98,
                                "fit_preference": "regular",
                                "pose": "front_relaxed",
                                "skin_tone": "medium",
                                "age_band": "adult",
                            },
                        },
                        "manual_quality_notes": {"overall": ""},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _preview_config() -> PreviewModelConfig:
    return PreviewModelConfig(
        run_id="flux-kontext",
        model="flux-kontext-apps/multi-image-kontext-pro",
        model_version=None,
        input_mapping="flux_kontext_multi_image",
        prompt_variant="flux-kontext-outfit-preview-v1",
    )


def _preview_generator(*, generated_bytes: bytes = b"generated-image") -> Mock:
    image_generator = Mock()
    image_generator.seed = 42
    image_generator.get_runtime_metadata.return_value = {
        "preview_model": "flux-kontext-apps/multi-image-kontext-pro",
        "preview_input_mapping": "flux_kontext_multi_image",
        "preview_prompt_version": "flux-kontext-outfit-preview-v1",
    }
    image_generator.generate_tryon_from_b64.return_value = base64.b64encode(
        generated_bytes
    ).decode("utf-8")
    return image_generator


def test_load_avatar_eval_cases_derives_profile_without_raw_detailed_measurements(
    tmp_path,
):
    manifest_path = _write_avatar_manifest(tmp_path)

    cases = load_avatar_eval_cases(manifest_path)

    assert len(cases) == 1
    case = cases[0]
    assert case.case_id == "avatar-upper-001"
    assert case.avatar_image_path == tmp_path / "avatar.png"
    assert case.product_image_path == tmp_path / "product.png"
    assert case.report_profile["input_mode"] == "detailed"
    assert case.report_profile["derived_profile"]["height_range"] == "tall"
    assert case.report_profile["derived_profile"] == case.derived_profile.model_dump(
        mode="json"
    )
    serialized = str(case.report_profile)
    assert "182" not in serialized
    assert "84" not in serialized
    assert "height_cm" not in serialized
    assert "weight_kg" not in serialized
    assert case.manual_quality_notes == {"overall": ""}


def test_build_avatar_dry_run_plan_contains_summary_and_no_raw_measurements(
    tmp_path,
):
    cases = load_avatar_eval_cases(_write_avatar_manifest(tmp_path))

    plan = build_avatar_dry_run_plan(cases, [_preview_config()])

    assert plan["summary"] == {
        "total_cases": 1,
        "preview_runs_per_case": 1,
        "total_preview_runs": 1,
    }
    planned_run = plan["planned_runs"][0]
    assert planned_run["case_id"] == "avatar-upper-001"
    assert planned_run["input_mode"] == "detailed"
    assert planned_run["derived_profile"]["height_range"] == "tall"
    assert planned_run["run_id"] == "flux-kontext"
    assert planned_run["model"] == "flux-kontext-apps/multi-image-kontext-pro"
    assert planned_run["input_mapping"] == "flux_kontext_multi_image"
    assert planned_run["prompt_variant"] == "flux-kontext-outfit-preview-v1"
    assert planned_run["avatar_prompt_variant"] == "avatar-garment-preview-context-v1"
    serialized = str(plan)
    assert "182" not in serialized
    assert "84" not in serialized
    for raw_field_name in (
        "height_cm",
        "weight_kg",
        "shoulder_width_cm",
        "chest_or_bust_cm",
        "waist_cm",
        "hip_cm",
    ):
        assert raw_field_name not in serialized


def test_avatar_eval_runner_writes_success_report(tmp_path):
    cases = load_avatar_eval_cases(_write_avatar_manifest(tmp_path))
    report_path = tmp_path / "avatar-report.json"
    image_generator = _preview_generator(generated_bytes=b"generated-image")

    report = AvatarEvalRunner().run_cases_with_preview_generators(
        cases=cases,
        preview_generators=[("flux-kontext", image_generator)],
        report_path=report_path,
    )

    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["preview_runs_per_case"] == 1
    assert report["summary"]["total_preview_runs"] == 1
    assert report["summary"]["succeeded"] == 1
    assert report["summary"]["failed"] == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    case_result = payload["cases"][0]
    assert case_result["status"] == "succeeded"
    assert case_result["input_hashes"]["avatar_image_sha256"] == file_sha256(
        tmp_path / "avatar.png"
    )
    assert case_result["input_hashes"]["product_image_sha256"] == file_sha256(
        tmp_path / "product.png"
    )
    preview_result = case_result["preview_results"][0]
    assert preview_result["model"] == "flux-kontext-apps/multi-image-kontext-pro"
    assert preview_result["input_mapping"] == "flux_kontext_multi_image"
    assert preview_result["prompt_version"] == "flux-kontext-outfit-preview-v1"
    assert len(preview_result["preview_context_prompt_sha256"]) == 64
    assert preview_result["preview_cache_key"].startswith("avatar-preview:v1:")
    generated_path = Path(preview_result["generated_image_path"])
    assert generated_path.exists()
    assert generated_path.read_bytes() == b"generated-image"
    generated_prompt = image_generator.generate_tryon_from_b64.call_args.kwargs[
        "inpainting_prompt"
    ]
    assert "personalized avatar mannequin" in generated_prompt


def test_avatar_eval_runner_records_preview_failure(tmp_path):
    cases = load_avatar_eval_cases(_write_avatar_manifest(tmp_path))
    report_path = tmp_path / "avatar-report.json"
    image_generator = _preview_generator()
    image_generator.generate_tryon_from_b64.side_effect = RuntimeError(
        "provider unavailable"
    )

    report = AvatarEvalRunner().run_cases_with_preview_generators(
        cases=cases,
        preview_generators=[("flux-kontext", image_generator)],
        report_path=report_path,
    )

    assert report["summary"]["succeeded"] == 0
    assert report["summary"]["failed"] == 1
    case_result = report["cases"][0]
    assert case_result["status"] == "failed"
    assert case_result["error"] == "One or more preview runs failed"
    preview_result = case_result["preview_results"][0]
    assert preview_result["status"] == "failed"
    assert preview_result["error"] == "provider unavailable"
    assert preview_result["generated_image_path"] is None
    assert preview_result["generated_image_bytes"] is None
    assert len(preview_result["preview_context_prompt_sha256"]) == 64
    assert preview_result["preview_cache_key"] is None


def test_avatar_eval_runner_rejects_invalid_base64_preview_output(tmp_path):
    cases = load_avatar_eval_cases(_write_avatar_manifest(tmp_path))
    report_path = tmp_path / "avatar-report.json"
    image_generator = _preview_generator()
    image_generator.generate_tryon_from_b64.return_value = "abcd####"

    report = AvatarEvalRunner().run_cases_with_preview_generators(
        cases=cases,
        preview_generators=[("flux-kontext", image_generator)],
        report_path=report_path,
    )

    assert report["summary"]["succeeded"] == 0
    assert report["summary"]["failed"] == 1
    preview_result = report["cases"][0]["preview_results"][0]
    assert preview_result["status"] == "failed"
    assert preview_result["generated_image_path"] is None
    assert preview_result["generated_image_bytes"] is None
    assert preview_result["preview_cache_key"] is None


def test_avatar_eval_runner_redacts_sensitive_preview_errors(tmp_path):
    cases = load_avatar_eval_cases(_write_avatar_manifest(tmp_path))
    report_path = tmp_path / "avatar-report.json"
    image_generator = _preview_generator()
    sensitive_token = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODkw"
    image_generator.generate_tryon_from_b64.side_effect = RuntimeError(
        "preview failed for /Users/long.vo/private/avatar.png "
        f"with token {sensitive_token}"
    )

    report = AvatarEvalRunner().run_cases_with_preview_generators(
        cases=cases,
        preview_generators=[("flux-kontext", image_generator)],
        report_path=report_path,
    )

    preview_result = report["cases"][0]["preview_results"][0]
    persisted_error = preview_result["error"]
    assert persisted_error is not None
    assert "preview failed" in persisted_error
    assert "/Users/" not in persisted_error
    assert "avatar.png" not in persisted_error
    assert sensitive_token not in persisted_error
