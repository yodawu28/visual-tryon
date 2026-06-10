import json
from pathlib import Path

from scripts.prepare_qwen_edit_smoke_data import prepare_qwen_edit_smoke_data


def test_prepare_qwen_edit_smoke_data_creates_inputs_and_manifest(tmp_path: Path):
    result = prepare_qwen_edit_smoke_data(data_dir=tmp_path)

    person_image = Path(result["person_image"])
    garment_image = Path(result["garment_image"])
    manifest = Path(result["manifest"])

    assert person_image.exists()
    assert garment_image.exists()
    assert manifest.exists()
    assert person_image.name == "kiosk-session-v1-smoke-front.png"
    assert garment_image.name == "garment-v1-smoke.webp"

    payload = json.loads(manifest.read_text("utf-8"))
    assert payload["person_image"] == str(person_image)
    assert payload["garment_image"] == str(garment_image)
    assert payload["garment_category"] == "upper"
    assert payload["catvton_cloth_type"] == "upper"
    assert "make runpod-qwen-edit-smoke" in payload["smoke_command"]
    assert "make runpod-catvton-smoke" in payload["catvton_smoke_command"]
    assert "RUNPOD_CATVTON_CLOTH_TYPE=upper" in payload["catvton_smoke_command"]
    assert "fixture_sources" in payload


def test_prepare_qwen_edit_smoke_data_does_not_overwrite_existing_by_default(
    tmp_path: Path,
):
    first = prepare_qwen_edit_smoke_data(data_dir=tmp_path)
    person_image = Path(first["person_image"])
    original_bytes = person_image.read_bytes()
    person_image.write_bytes(b"custom-image")

    second = prepare_qwen_edit_smoke_data(data_dir=tmp_path)

    assert second["created"] == []
    assert person_image.read_bytes() == b"custom-image"
    assert original_bytes != b"custom-image"


def test_prepare_qwen_edit_smoke_data_can_overwrite_existing(tmp_path: Path):
    first = prepare_qwen_edit_smoke_data(data_dir=tmp_path)
    person_image = Path(first["person_image"])
    person_image.write_bytes(b"custom-image")

    second = prepare_qwen_edit_smoke_data(data_dir=tmp_path, overwrite=True)

    assert str(person_image) in second["created"]
    assert person_image.read_bytes() != b"custom-image"


def test_prepare_qwen_edit_smoke_data_prefers_fixture_images(tmp_path: Path):
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    front = fixture_dir / "front.png"
    garment = fixture_dir / "garment.webp"
    front.write_bytes(b"front-fixture")
    garment.write_bytes(b"garment-fixture")

    result = prepare_qwen_edit_smoke_data(
        data_dir=tmp_path / "runtime",
        fixture_dir=fixture_dir,
    )

    person_image = Path(result["person_image"])
    garment_image = Path(result["garment_image"])
    manifest = Path(result["manifest"])
    payload = json.loads(manifest.read_text("utf-8"))

    assert person_image.read_bytes() == b"front-fixture"
    assert garment_image.read_bytes() == b"garment-fixture"
    assert payload["fixture_sources"]["person_image_exists"] is True
    assert payload["fixture_sources"]["garment_image_exists"] is True


def test_prepare_qwen_edit_smoke_data_records_garment_category(tmp_path: Path):
    result = prepare_qwen_edit_smoke_data(
        data_dir=tmp_path,
        garment_category="lower",
    )

    manifest = Path(result["manifest"])
    payload = json.loads(manifest.read_text("utf-8"))

    assert result["garment_category"] == "lower"
    assert result["catvton_cloth_type"] == "lower"
    assert payload["garment_category"] == "lower"
    assert payload["catvton_cloth_type"] == "lower"
    assert "RUNPOD_CATVTON_CLOTH_TYPE=lower" in payload["catvton_smoke_command"]
