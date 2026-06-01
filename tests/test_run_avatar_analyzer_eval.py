import json
from pathlib import Path
from unittest.mock import Mock

import scripts.run_avatar_analyzer_eval as run_avatar_analyzer_eval
from src.modules.avatar_preview.profile import (
    AvatarFraming,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)
from src.modules.avatar_preview.tryon_analyzer import TryOnIntent


def _write_manifest(tmp_path: Path) -> Path:
    avatar_path = tmp_path / "avatar.png"
    product_path = tmp_path / "jersey.png"
    avatar_path.write_bytes(b"avatar")
    product_path.write_bytes(b"garment")
    manifest_path = tmp_path / "avatar_analyzer_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "short-sleeve-jersey-001",
                        "avatar_image_path": "avatar.png",
                        "product_image_path": "jersey.png",
                        "expected": {
                            "garment_region": "upper_body",
                            "garment_type": "jersey",
                            "sleeve_length": "short_sleeve",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _intent() -> TryOnIntent:
    return TryOnIntent(
        garment_region=GarmentRegion.UPPER_BODY,
        garment_type=GarmentType.JERSEY,
        sleeve_length=GarmentSleeveLength.SHORT_SLEEVE,
        neckline="v-neck",
        dominant_colors=["mint green", "navy blue"],
        logo_or_text="Yonex mark and Korea flag",
        pattern="subtle geometric pattern",
        risk_notes=["short sleeve fidelity is important"],
        recommended_avatar_framing=AvatarFraming.FULL_BODY,
    )


def test_parse_args_supports_analyzer_eval_options(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"

    args = run_avatar_analyzer_eval.parse_args(
        [
            "--manifest",
            str(manifest_path),
            "--report-path",
            str(report_path),
            "--model",
            "qwen2.5vl:7b",
            "--model",
            "gemma3:4b",
            "--dry-run",
        ]
    )

    assert args.manifest == manifest_path
    assert args.report_path == report_path
    assert args.models == ["qwen2.5vl:7b", "gemma3:4b"]
    assert args.dry_run is True


def test_main_dry_run_prints_planned_analyzer_runs(tmp_path, capsys):
    manifest_path = _write_manifest(tmp_path)

    return_code = run_avatar_analyzer_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--model",
            "qwen2.5vl:7b",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert return_code == 0
    assert payload["summary"]["total_cases"] == 1
    assert payload["summary"]["total_analyzer_runs"] == 1
    planned_run = payload["planned_runs"][0]
    assert planned_run["case_id"] == "short-sleeve-jersey-001"
    assert planned_run["model"] == "qwen2.5vl:7b"
    assert planned_run["expected"]["sleeve_length"] == "short_sleeve"


def test_main_non_dry_run_writes_report_with_expected_field_scores(
    tmp_path,
    monkeypatch,
):
    manifest_path = _write_manifest(tmp_path)
    report_path = tmp_path / "report.json"
    analyzer = Mock()
    analyzer.analyze_images.return_value = _intent()
    analyzer.get_runtime_metadata.return_value = {
        "provider": "ollama",
        "model": "qwen2.5vl:7b",
        "analyzer_prompt_version": "avatar-tryon-analyzer-v1",
    }

    monkeypatch.setattr(
        run_avatar_analyzer_eval,
        "build_analyzer_from_args",
        Mock(return_value=analyzer),
    )

    return_code = run_avatar_analyzer_eval.main(
        [
            "--manifest",
            str(manifest_path),
            "--report-path",
            str(report_path),
            "--model",
            "qwen2.5vl:7b",
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    result = report["cases"][0]["analyzer_results"][0]

    assert return_code == 0
    assert report["summary"]["succeeded"] == 1
    assert result["status"] == "succeeded"
    assert result["intent"]["garment_type"] == "jersey"
    assert result["field_scores"] == {
        "garment_region": True,
        "garment_type": True,
        "sleeve_length": True,
    }
    analyzer.analyze_images.assert_called_once_with(
        avatar_image=b"avatar",
        garment_image=b"garment",
    )
