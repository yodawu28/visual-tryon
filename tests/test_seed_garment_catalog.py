from pathlib import Path

from PIL import Image

from scripts.seed_garment_catalog import seed_garment_catalog
from src.modules.kiosk_tryon.garment_registry import GarmentRegistry
from src.modules.kiosk_tryon.size_chart_registry import SizeChartRegistry


def test_seed_garment_catalog_imports_default_images_with_size_chart(tmp_path):
    source_dir = tmp_path / "catalog"
    storage_dir = tmp_path / "garments"
    size_chart_db_path = tmp_path / "size_charts.sqlite3"
    source_dir.mkdir()
    _write_webp(source_dir / "garment-1.webp", color=(255, 0, 0))
    _write_webp(source_dir / "garment-2.webp", color=(0, 255, 0))
    size_chart = SizeChartRegistry(db_path=size_chart_db_path).create_size_chart(
        name="VN Generic Adult Tops Regular",
        country_code="VN",
        region="Vietnam",
        category="tops",
        garment_type="regular_top",
        source_type="generic_reference",
        source_url=None,
        last_verified_at=None,
        size_chart=[{"size": "M", "chest_cm": 96}],
        notes=None,
    )

    result = seed_garment_catalog(
        source_dir=source_dir,
        storage_dir=storage_dir,
        size_chart_db_path=size_chart_db_path,
    )

    assert result["created_count"] == 2
    assert result["skipped_count"] == 0
    registry = GarmentRegistry(
        db_path=storage_dir / "garments.sqlite3",
        image_dir=storage_dir / "images",
    )
    records = registry.list_garments(limit=10)
    assert {record.original_filename for record in records} == {
        "garment-1.webp",
        "garment-2.webp",
    }
    assert {record.size_chart_id for record in records} == {size_chart.size_chart_id}


def test_seed_garment_catalog_skips_existing_images(tmp_path):
    source_dir = tmp_path / "catalog"
    storage_dir = tmp_path / "garments"
    source_dir.mkdir()
    _write_webp(source_dir / "garment-1.webp", color=(255, 0, 0))

    first = seed_garment_catalog(source_dir=source_dir, storage_dir=storage_dir)
    second = seed_garment_catalog(source_dir=source_dir, storage_dir=storage_dir)

    assert first["created_count"] == 1
    assert second["created_count"] == 0
    assert second["skipped_count"] == 1


def _write_webp(path: Path, *, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (32, 32), color).save(path, format="WEBP")
