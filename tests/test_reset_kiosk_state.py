import json
from pathlib import Path

import scripts.reset_kiosk_state as reset_kiosk_state
from src.modules.kiosk_tryon.size_chart_registry import SizeChartRegistry


def test_reset_kiosk_state_defaults_to_dry_run(tmp_path: Path):
    data_dir = tmp_path / "data"
    size_chart_db = data_dir / "size_charts" / "size_charts.sqlite3"
    garment_db = data_dir / "garments" / "garments.sqlite3"
    size_chart_db.parent.mkdir(parents=True)
    garment_db.parent.mkdir(parents=True)
    size_chart_db.write_bytes(b"size-chart-db")
    garment_db.write_bytes(b"garment-db")

    result = reset_kiosk_state.reset_kiosk_state(data_dir=data_dir)

    assert result["execute"] is False
    assert result["deleted_count"] == 0
    assert size_chart_db.exists()
    assert garment_db.exists()
    assert {target["exists"] for target in result["planned_targets"]} == {True}


def test_reset_kiosk_state_execute_deletes_selected_sqlite_files(tmp_path: Path):
    data_dir = tmp_path / "data"
    size_chart_db = data_dir / "size_charts" / "size_charts.sqlite3"
    garment_db = data_dir / "garments" / "garments.sqlite3"
    size_chart_db.parent.mkdir(parents=True)
    garment_db.parent.mkdir(parents=True)
    size_chart_db.write_bytes(b"size-chart-db")
    garment_db.write_bytes(b"garment-db")

    result = reset_kiosk_state.reset_kiosk_state(data_dir=data_dir, execute=True)

    assert result["deleted_count"] == 2
    assert size_chart_db.exists() is False
    assert garment_db.exists() is False


def test_reset_kiosk_state_can_clear_runtime_files(tmp_path: Path):
    data_dir = tmp_path / "data"
    capture = data_dir / "kiosk_sessions" / "captures" / "front.png"
    job = data_dir / "jobs" / "metadata" / "job.json"
    capture.parent.mkdir(parents=True)
    job.parent.mkdir(parents=True)
    capture.write_bytes(b"image")
    job.write_text("{}", encoding="utf-8")

    result = reset_kiosk_state.reset_kiosk_state(
        data_dir=data_dir,
        execute=True,
        include_runtime_files=True,
    )

    assert any("captures" in path for path in result["deleted"])
    assert any("metadata" in path for path in result["deleted"])
    assert capture.exists() is False
    assert job.exists() is False
    assert capture.parent.exists()
    assert job.parent.exists()


def test_reset_kiosk_state_can_seed_default_size_charts_after_reset(tmp_path: Path):
    data_dir = tmp_path / "data"
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "size_charts": [
                    {
                        "name": "VN Generic Adult Tops Regular",
                        "country_code": "VN",
                        "category": "tops",
                        "garment_type": "regular_top",
                        "source_type": "generic_reference",
                        "size_chart": [{"size": "M", "chest_cm": 96}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = reset_kiosk_state.reset_kiosk_state(
        data_dir=data_dir,
        execute=True,
        seed_default_size_charts=True,
        seed_path=seed_path,
    )

    assert result["seed_default_size_charts"]["created_count"] == 1
    registry = SizeChartRegistry(
        db_path=data_dir / "size_charts" / "size_charts.sqlite3"
    )
    records = registry.list_size_charts(country_code="VN", category="tops")
    assert len(records) == 1
