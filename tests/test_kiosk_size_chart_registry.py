import pytest

from src.modules.kiosk_tryon.size_chart_registry import SizeChartRegistry


def test_create_size_chart_stores_market_chart(tmp_path):
    registry = SizeChartRegistry(db_path=tmp_path / "size_charts.sqlite3")

    record = registry.create_size_chart(
        name="VN tops",
        country_code="vn",
        region="Vietnam",
        category="tops",
        garment_type="jersey",
        source_type="generic_reference",
        source_url="https://example.com/size-chart",
        last_verified_at="2026-06-04",
        size_chart=[{"size": "M", "chest_cm": 96, "waist_cm": 84}],
        notes="baseline",
    )

    assert record.size_chart_id.startswith("size-chart:v1:")
    assert record.country_code == "VN"
    assert record.category == "tops"
    assert record.source_type == "generic_reference"
    assert record.source_url == "https://example.com/size-chart"
    assert record.last_verified_at == "2026-06-04"
    assert record.size_chart == [
        {"size": "M", "chest_cm": 96.0, "waist_cm": 84.0}
    ]

    loaded = registry.get_size_chart(record.size_chart_id)
    assert loaded == record


def test_list_size_charts_filters_by_market_and_category(tmp_path):
    registry = SizeChartRegistry(db_path=tmp_path / "size_charts.sqlite3")
    vn = registry.create_size_chart(
        name="VN tops",
        country_code="VN",
        category="tops",
        size_chart=[{"size": "M", "chest_cm": 96}],
    )
    registry.create_size_chart(
        name="US bottoms",
        country_code="US",
        category="bottoms",
        size_chart=[{"size": "M", "waist_cm": 84}],
    )

    records = registry.list_size_charts(country_code="vn", category="tops")

    assert [record.size_chart_id for record in records] == [vn.size_chart_id]


def test_create_size_chart_requires_rows(tmp_path):
    registry = SizeChartRegistry(db_path=tmp_path / "size_charts.sqlite3")

    with pytest.raises(ValueError, match="size_chart must include"):
        registry.create_size_chart(
            name="VN tops",
            country_code="VN",
            category="tops",
            size_chart=[],
        )
