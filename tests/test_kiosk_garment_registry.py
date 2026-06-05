from io import BytesIO

import pytest
from PIL import Image

from src.modules.kiosk_tryon.garment_registry import GarmentRegistry


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_create_garment_stores_image_and_metadata(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )

    record = registry.create_garment(
        image_bytes=_png_bytes(),
        category="tops",
        name="Mint jersey",
        garment_type="jersey",
        original_filename="jersey.png",
    )

    assert record.garment_id.startswith("garment:v1:")
    assert record.name == "Mint jersey"
    assert record.category == "tops"
    assert record.garment_type == "jersey"
    assert record.storage_provider == "local"
    assert record.storage_uri.endswith(".png")
    assert record.mime_type == "image/png"
    assert record.original_filename == "jersey.png"
    assert record.size_chart_id is None
    assert record.size_chart == []
    assert registry.exists(record.garment_id) is True

    stored_path = tmp_path / "images" / f"{record.garment_id.replace(':', '-')}.png"
    assert stored_path.exists()
    assert stored_path.read_bytes() == _png_bytes()

    loaded = registry.get_garment(record.garment_id)
    assert loaded == record
    assert registry.read_image(record.garment_id) == _png_bytes()


def test_create_garment_stores_size_chart(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )

    record = registry.create_garment(
        image_bytes=_png_bytes(),
        category="tops",
        size_chart=[{"size": "M", "chest_cm": 96}],
    )

    assert record.size_chart == [{"size": "M", "chest_cm": 96.0}]
    loaded = registry.get_garment(record.garment_id)
    assert loaded is not None
    assert loaded.size_chart == [{"size": "M", "chest_cm": 96.0}]


def test_create_garment_stores_size_chart_id(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )

    record = registry.create_garment(
        image_bytes=_png_bytes(),
        category="tops",
        size_chart_id="size-chart:v1:vn",
    )

    assert record.size_chart_id == "size-chart:v1:vn"
    loaded = registry.get_garment(record.garment_id)
    assert loaded is not None
    assert loaded.size_chart_id == "size-chart:v1:vn"


def test_list_garments_returns_newest_first(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )
    first = registry.create_garment(image_bytes=_png_bytes(), category="tops")
    second = registry.create_garment(image_bytes=_png_bytes(), category="bottoms")

    records = registry.list_garments()

    assert [record.garment_id for record in records] == [
        second.garment_id,
        first.garment_id,
    ]


def test_create_garment_rejects_invalid_category(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )

    with pytest.raises(ValueError, match="category must be one of"):
        registry.create_garment(image_bytes=_png_bytes(), category="upper_body")


def test_create_garment_rejects_invalid_image(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )

    with pytest.raises(ValueError, match="valid PNG, JPEG, or WEBP"):
        registry.create_garment(image_bytes=b"not-an-image", category="tops")


def test_create_garment_rejects_oversized_image(tmp_path):
    registry = GarmentRegistry(
        db_path=tmp_path / "garments.sqlite3",
        image_dir=tmp_path / "images",
    )

    with pytest.raises(ValueError, match="exceeds the configured upload limit"):
        registry.create_garment(
            image_bytes=_png_bytes(),
            category="tops",
            max_size_bytes=1,
        )
