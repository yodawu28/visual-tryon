import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import scripts.run_avatar_preview_eval as run_avatar_preview_eval


def _write_manifest(tmp_path: Path) -> Path:
    avatar_path = tmp_path / "avatar.png"
    product_path = tmp_path / "product.png"
    avatar_path.write_bytes(b"avatar-image")
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "avatar_manifest.json"
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


def _write_generated_manifest(tmp_path: Path) -> Path:
    product_path = tmp_path / "product.png"
    product_path.write_bytes(b"product-image")
    manifest_path = tmp_path / "avatar_generated_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "avatar-upper-generated-001",
                        "avatar_image_source": "generated_synthetic_person_photo",
                        "product_image_path": "product.png",
                        "body_profile": {
                            "input_mode": "basic",
                            "basic": {
                                "gender_presentation": "male",
                                "body_build": "athletic",
                                "height_range": "tall",
                                "shoulder_width": "broad",
                                "fit_preference": "regular",
                                "pose": "front_relaxed",
                                "skin_tone": "not_specified",
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


def _write_lower_body_generated_manifest(tmp_path: Path) -> Path:
    product_path = tmp_path / "pants.png"
    product_path.write_bytes(b"pants-image")
    manifest_path = tmp_path / "avatar_lower_body_generated_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "avatar-lower-generated-001",
                        "avatar_image_source": "generated_synthetic_person_photo",
                        "garment_region": "lower_body",
                        "product_image_path": "pants.png",
                        "body_profile": {
                            "input_mode": "basic",
                            "basic": {
                                "gender_presentation": "male",
                                "body_build": "athletic",
                                "height_range": "tall",
                                "shoulder_width": "broad",
                                "fit_preference": "regular",
                                "pose": "front_relaxed",
                                "skin_tone": "not_specified",
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


def _write_matrix(tmp_path: Path) -> Path:
    matrix_path = tmp_path / "model_matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen-avatar-current",
                        "model": "qwen/qwen-image-edit-2511",
                        "model_version": None,
                        "input_mapping": "multi_image_edit",
                        "prompt_variant": "avatar-qwen-multimodal-preview-v1",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return matrix_path


def _write_matrix_without_prompt_variant(tmp_path: Path) -> Path:
    matrix_path = tmp_path / "model_matrix_without_prompt_variant.json"
    matrix_path.write_text(
        json.dumps(
            {
                "preview_models": [
                    {
                        "run_id": "qwen-avatar-current",
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
    return matrix_path


def test_parse_args_supports_avatar_preview_eval_options(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    matrix_path = tmp_path / "model_matrix.json"

    args = run_avatar_preview_eval.parse_args(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--limit-cases",
            "2",
            "--dry-run",
        ]
    )

    assert args.manifest == manifest_path
    assert args.model_matrix == matrix_path
    assert args.limit_cases == 2
    assert args.dry_run is True


def test_main_dry_run_prints_plan_and_does_not_instantiate_preview_generators(
    tmp_path,
    monkeypatch,
    capsys,
):
    manifest_path = _write_manifest(tmp_path)
    matrix_path = _write_matrix(tmp_path)
    generator_builder = Mock(
        side_effect=AssertionError("preview generator instantiated")
    )
    monkeypatch.setattr(
        run_avatar_preview_eval,
        "build_avatar_preview_generator_from_config",
        generator_builder,
    )

    return_code = run_avatar_preview_eval.main(
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
                "case_id": "avatar-upper-001",
                "input_mode": "detailed",
                "derived_profile": {
                    "age_band": "adult",
                    "avatar_style": "synthetic_person_photo",
                    "body_build": "athletic",
                    "fit_preference": "regular",
                    "gender_presentation": "male",
                    "height_range": "tall",
                    "pose": "front_relaxed",
                    "shoulder_width": "broad",
                    "skin_tone": "medium",
                },
                "run_id": "qwen-avatar-current",
                "model": "qwen/qwen-image-edit-2511",
                "input_mapping": "multi_image_edit",
                "prompt_variant": "avatar-qwen-multimodal-preview-v1",
                "avatar_prompt_variant": "avatar-garment-preview-context-v4",
                "avatar_image_source": "provided_image",
                "garment_type": None,
                "garment_region": "upper_body",
                "garment_sleeve_length": "unknown",
                "fashn_category": "tops",
                "avatar_framing": "upper_body",
            }
        ],
    }
    generator_builder.assert_not_called()


def test_main_dry_run_defaults_avatar_prompt_variant(tmp_path, capsys):
    manifest_path = _write_manifest(tmp_path)
    matrix_path = _write_matrix_without_prompt_variant(tmp_path)

    return_code = run_avatar_preview_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert return_code == 0
    assert (
        payload["planned_runs"][0]["prompt_variant"]
        == "avatar-qwen-multimodal-preview-v1"
    )


def test_main_dry_run_maps_lower_body_to_full_body_avatar(tmp_path, capsys):
    manifest_path = _write_lower_body_generated_manifest(tmp_path)
    matrix_path = _write_matrix(tmp_path)

    return_code = run_avatar_preview_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--dry-run",
        ]
    )

    planned_run = json.loads(capsys.readouterr().out)["planned_runs"][0]

    assert return_code == 0
    assert planned_run["garment_region"] == "lower_body"
    assert planned_run["garment_sleeve_length"] == "unknown"
    assert planned_run["fashn_category"] == "bottoms"
    assert planned_run["avatar_framing"] == "full_body"


def test_main_dry_run_requires_model_matrix(tmp_path):
    manifest_path = _write_manifest(tmp_path)

    with pytest.raises(ValueError, match="--model-matrix is required"):
        run_avatar_preview_eval.main(
            [
                "--manifest",
                str(manifest_path),
                "--dry-run",
            ]
        )


def test_main_non_dry_run_uses_avatar_factory_and_runner(tmp_path, monkeypatch):
    manifest_path = _write_manifest(tmp_path)
    matrix_path = _write_matrix(tmp_path)
    report_path = tmp_path / "report.json"
    image_generator = object()
    generator_builder = Mock(return_value=image_generator)
    captured = {}

    class FakeAvatarEvalRunner:
        def run_cases_with_preview_generators(
            self,
            *,
            cases,
            preview_generators,
            report_path,
        ):
            captured["cases"] = cases
            captured["preview_generators"] = preview_generators
            captured["report_path"] = report_path
            return {
                "summary": {
                    "total_cases": len(cases),
                    "preview_runs_per_case": len(preview_generators),
                    "total_preview_runs": len(preview_generators),
                    "succeeded": 0,
                    "failed": 1,
                }
            }

    monkeypatch.setattr(
        run_avatar_preview_eval,
        "build_avatar_preview_generator_from_config",
        generator_builder,
    )
    monkeypatch.setattr(
        run_avatar_preview_eval,
        "AvatarEvalRunner",
        FakeAvatarEvalRunner,
    )

    return_code = run_avatar_preview_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--report-path",
            str(report_path),
        ]
    )

    assert return_code == 1
    generator_builder.assert_called_once()
    assert captured["preview_generators"] == [("qwen-avatar-current", image_generator)]
    assert captured["report_path"] == report_path


def test_main_non_dry_run_can_generate_missing_avatars(tmp_path, monkeypatch):
    manifest_path = _write_generated_manifest(tmp_path)
    matrix_path = _write_matrix(tmp_path)
    report_path = tmp_path / "report.json"
    avatar_cache_dir = tmp_path / "avatar-cache"
    image_generator = object()
    avatar_generator = object()
    generator_builder = Mock(return_value=image_generator)
    avatar_builder = Mock(return_value=avatar_generator)
    captured = {}

    class FakeAvatarEvalRunner:
        def run_cases_with_preview_generators(
            self,
            *,
            cases,
            preview_generators,
            report_path,
            avatar_generator,
            avatar_cache_dir,
        ):
            captured["cases"] = cases
            captured["preview_generators"] = preview_generators
            captured["report_path"] = report_path
            captured["avatar_generator"] = avatar_generator
            captured["avatar_cache_dir"] = avatar_cache_dir
            return {
                "summary": {
                    "total_cases": len(cases),
                    "preview_runs_per_case": len(preview_generators),
                    "total_preview_runs": len(preview_generators),
                    "succeeded": 1,
                    "failed": 0,
                }
            }

    monkeypatch.setattr(
        run_avatar_preview_eval,
        "build_avatar_preview_generator_from_config",
        generator_builder,
    )
    monkeypatch.setattr(
        run_avatar_preview_eval,
        "build_synthetic_avatar_generator",
        avatar_builder,
    )
    monkeypatch.setattr(
        run_avatar_preview_eval,
        "AvatarEvalRunner",
        FakeAvatarEvalRunner,
    )

    return_code = run_avatar_preview_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model-matrix",
            str(matrix_path),
            "--report-path",
            str(report_path),
            "--generate-missing-avatars",
            "--avatar-cache-dir",
            str(avatar_cache_dir),
        ]
    )

    assert return_code == 0
    generator_builder.assert_called_once()
    avatar_builder.assert_called_once()
    assert captured["preview_generators"] == [("qwen-avatar-current", image_generator)]
    assert captured["avatar_generator"] is avatar_generator
    assert captured["avatar_cache_dir"] == avatar_cache_dir


def test_main_generate_avatars_only_does_not_require_model_matrix_or_preview(
    tmp_path,
    monkeypatch,
):
    manifest_path = _write_generated_manifest(tmp_path)
    report_path = tmp_path / "avatar-only-report.json"
    avatar_cache_dir = tmp_path / "avatar-cache"
    avatar_generator = object()
    avatar_builder = Mock(return_value=avatar_generator)
    preview_builder = Mock(side_effect=AssertionError("preview should not run"))
    captured = {}

    class FakeAvatarEvalRunner:
        def generate_avatar_images_for_cases(
            self,
            *,
            cases,
            avatar_generator,
            avatar_cache_dir,
            report_path,
        ):
            captured["cases"] = cases
            captured["avatar_generator"] = avatar_generator
            captured["avatar_cache_dir"] = avatar_cache_dir
            captured["report_path"] = report_path
            return {
                "summary": {
                    "total_cases": len(cases),
                    "generated": 1,
                    "cache_hits": 0,
                    "failed": 0,
                }
            }

    monkeypatch.setattr(
        run_avatar_preview_eval,
        "build_synthetic_avatar_generator",
        avatar_builder,
    )
    monkeypatch.setattr(
        run_avatar_preview_eval,
        "build_avatar_preview_generator_from_config",
        preview_builder,
    )
    monkeypatch.setattr(
        run_avatar_preview_eval,
        "AvatarEvalRunner",
        FakeAvatarEvalRunner,
    )

    return_code = run_avatar_preview_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--generate-avatars-only",
            "--avatar-cache-dir",
            str(avatar_cache_dir),
            "--report-path",
            str(report_path),
        ]
    )

    assert return_code == 0
    avatar_builder.assert_called_once()
    preview_builder.assert_not_called()
    assert captured["avatar_generator"] is avatar_generator
    assert captured["avatar_cache_dir"] == avatar_cache_dir
    assert captured["report_path"] == report_path
