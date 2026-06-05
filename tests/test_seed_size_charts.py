import json
from pathlib import Path

import pytest

import scripts.seed_size_charts as seed_size_charts
from src.modules.kiosk_tryon.size_chart_registry import SizeChartRegistry


def test_load_seed_payload_requires_size_charts_array(tmp_path: Path):
    seed_path = tmp_path / "bad_seed.json"
    seed_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="size_charts array"):
        seed_size_charts.load_seed_payload(seed_path)


def test_seed_size_charts_creates_catalog_records(tmp_path: Path):
    seed_path = _write_seed_file(tmp_path)
    db_path = tmp_path / "size_charts.sqlite3"

    result = seed_size_charts.seed_size_charts(
        seed_path=seed_path,
        db_path=db_path,
    )

    assert result["created_count"] == 1
    assert result["skipped_count"] == 0
    registry = SizeChartRegistry(db_path=db_path)
    records = registry.list_size_charts(country_code="VN", category="tops")
    assert len(records) == 1
    assert records[0].source_type == "generic_reference"
    assert records[0].size_chart == [{"size": "M", "chest_cm": 96.0}]


def test_seed_size_charts_is_idempotent(tmp_path: Path):
    seed_path = _write_seed_file(tmp_path)
    db_path = tmp_path / "size_charts.sqlite3"

    first = seed_size_charts.seed_size_charts(seed_path=seed_path, db_path=db_path)
    second = seed_size_charts.seed_size_charts(seed_path=seed_path, db_path=db_path)

    assert first["created_count"] == 1
    assert second["created_count"] == 0
    assert second["skipped_count"] == 1


def test_seed_size_charts_dry_run_does_not_create_records(tmp_path: Path):
    seed_path = _write_seed_file(tmp_path)
    db_path = tmp_path / "size_charts.sqlite3"

    result = seed_size_charts.seed_size_charts(
        seed_path=seed_path,
        db_path=db_path,
        dry_run=True,
    )

    assert result["created_count"] == 1
    registry = SizeChartRegistry(db_path=db_path)
    assert registry.list_size_charts(country_code="VN", category="tops") == []


def _write_seed_file(tmp_path: Path) -> Path:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "size_charts": [
                    {
                        "name": "VN Generic Adult Tops Regular",
                        "country_code": "VN",
                        "region": "Vietnam",
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
    return seed_path
