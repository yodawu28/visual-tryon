import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import scripts.manage_data_cache as manage_data_cache


def test_collect_data_summary_groups_top_level_directories(tmp_path: Path):
    (tmp_path / "avatar_cache").mkdir()
    (tmp_path / "avatar_cache" / "avatar.png").write_bytes(b"avatar")
    (tmp_path / "eval" / "reports").mkdir(parents=True)
    (tmp_path / "eval" / "reports" / "report.json").write_text(
        "{}",
        encoding="utf-8",
    )

    summary = manage_data_cache.collect_data_summary(tmp_path)

    assert summary["total_files"] == 2
    assert summary["total_size_bytes"] == len(b"avatar") + len(b"{}")
    assert summary["top_level"]["avatar_cache"]["file_count"] == 1
    assert summary["top_level"]["eval"]["file_count"] == 1


def test_prune_cache_files_defaults_to_dry_run(tmp_path: Path):
    cache_dir = tmp_path / "avatar_cache"
    old_image = cache_dir / "avatars" / "avatar-v1-old.png"
    old_metadata = cache_dir / "avatars" / "avatar-v1-old.json"
    old_image.parent.mkdir(parents=True)
    old_image.write_bytes(b"old-avatar")
    old_metadata.write_text("{}", encoding="utf-8")
    now = datetime(2026, 6, 1, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=30)).timestamp()
    old_image.touch()
    old_metadata.touch()
    old_image_mtime = old_timestamp
    old_metadata_mtime = old_timestamp
    os.utime(old_image, (old_image_mtime, old_image_mtime))
    os.utime(old_metadata, (old_metadata_mtime, old_metadata_mtime))

    plan = manage_data_cache.build_prune_plan(
        cache_dir,
        older_than_days=7,
        now=now,
    )
    result = manage_data_cache.prune_cache_files(plan, execute=False)

    assert {entry.path for entry in plan.entries} == {old_image, old_metadata}
    assert result["deleted_count"] == 0
    assert result["planned_count"] == 2
    assert old_image.exists()
    assert old_metadata.exists()


def test_prune_cache_files_execute_deletes_planned_files(tmp_path: Path):
    cache_dir = tmp_path / "avatar_cache"
    old_image = cache_dir / "previews" / "avatar-preview-v1-old.png"
    old_metadata = cache_dir / "previews" / "avatar-preview-v1-old.json"
    old_image.parent.mkdir(parents=True)
    old_image.write_bytes(b"old-preview")
    old_metadata.write_text("{}", encoding="utf-8")
    now = datetime(2026, 6, 1, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=30)).timestamp()
    os.utime(old_image, (old_timestamp, old_timestamp))
    os.utime(old_metadata, (old_timestamp, old_timestamp))
    plan = manage_data_cache.build_prune_plan(
        cache_dir,
        older_than_days=7,
        now=now,
    )

    result = manage_data_cache.prune_cache_files(plan, execute=True)

    assert result["deleted_count"] == 2
    assert old_image.exists() is False
    assert old_metadata.exists() is False
