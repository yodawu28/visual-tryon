import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import scripts.run_fashn_vton_colab_eval as run_fashn_vton_colab_eval


def _write_manifest(tmp_path: Path, *, include_avatar: bool = True) -> Path:
    avatar_path = tmp_path / "avatar.png"
    product_path = tmp_path / "product.png"
    avatar_path.write_bytes(b"avatar-image")
    product_path.write_bytes(b"product-image")
    raw_case = {
        "case_id": "avatar-upper-001",
        "garment_type": "jersey",
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
    if include_avatar:
        raw_case["avatar_image_path"] = "avatar.png"
    manifest_path = tmp_path / "fashn_manifest.json"
    manifest_path.write_text(
        json.dumps({"cases": [raw_case]}),
        encoding="utf-8",
    )
    return manifest_path


def test_parse_args_supports_fashn_colab_options(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"

    args = run_fashn_vton_colab_eval.parse_args(
        [
            "--manifest",
            str(manifest_path),
            "--report-path",
            str(report_path),
            "--limit-cases",
            "1",
            "--command-template",
            "python infer.py",
            "--dry-run",
        ]
    )

    assert args.manifest == manifest_path
    assert args.report_path == report_path
    assert args.limit_cases == 1
    assert args.command_template == "python infer.py"
    assert args.dry_run is True


def test_main_dry_run_prints_fashn_plan(tmp_path, capsys):
    manifest_path = _write_manifest(tmp_path)

    return_code = run_fashn_vton_colab_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert return_code == 0
    assert payload["summary"]["total_preview_runs"] == 1
    planned_run = payload["planned_runs"][0]
    assert planned_run["run_id"] == "fashn_vton_local"
    assert planned_run["input_mapping"] == "local_fashn_vton"
    assert planned_run["prompt_variant"] == "fashn-vton-local-v1"
    assert planned_run["garment_type"] == "jersey"
    assert planned_run["garment_sleeve_length"] == "short_sleeve"
    assert planned_run["fashn_category"] == "tops"


def test_main_non_dry_run_uses_local_fashn_generator_and_runner(
    tmp_path,
    monkeypatch,
):
    manifest_path = _write_manifest(tmp_path)
    report_path = tmp_path / "report.json"
    generator = object()
    generator_builder = Mock(return_value=generator)
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
                    "succeeded": 1,
                    "failed": 0,
                }
            }

    monkeypatch.setattr(
        run_fashn_vton_colab_eval,
        "build_fashn_generator_from_args",
        generator_builder,
    )
    monkeypatch.setattr(
        run_fashn_vton_colab_eval,
        "AvatarEvalRunner",
        FakeAvatarEvalRunner,
    )

    return_code = run_fashn_vton_colab_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--report-path",
            str(report_path),
            "--command-template",
            "python infer.py",
        ]
    )

    assert return_code == 0
    generator_builder.assert_called_once()
    assert captured["preview_generators"] == [("fashn_vton_local", generator)]
    assert captured["report_path"] == report_path
    assert captured["cases"][0].fashn_category == "tops"


def test_main_non_dry_run_requires_provided_avatar_image(tmp_path):
    manifest_path = _write_manifest(tmp_path, include_avatar=False)

    with pytest.raises(ValueError, match="requires avatar_image_path"):
        run_fashn_vton_colab_eval.main(
            [
                "--manifest",
                str(manifest_path),
                "--command-template",
                "python infer.py",
            ]
        )
