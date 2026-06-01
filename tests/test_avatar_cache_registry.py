from pathlib import Path

from src.modules.avatar_preview.cache_registry import (
    AvatarCacheRegistry,
    CacheArtifactRecord,
)


def test_cache_registry_upserts_and_summarizes_artifacts(tmp_path: Path):
    image_path = tmp_path / "avatars" / "avatar-v1-abc.png"
    metadata_path = tmp_path / "avatars" / "avatar-v1-abc.json"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"avatar-image")
    metadata_path.write_text("{}", encoding="utf-8")
    registry = AvatarCacheRegistry(tmp_path / "cache_index.sqlite3")

    registry.upsert_artifact(
        CacheArtifactRecord(
            cache_key="avatar:v1:abc",
            artifact_kind="avatar",
            image_path=image_path,
            metadata_path=metadata_path,
            model="black-forest-labs/flux-schnell",
            prompt_version="avatar-body-profile-v4",
            image_sha256="avatar-sha",
            metadata={"garment_region": "upper_body"},
        )
    )

    loaded = registry.get_artifact("avatar:v1:abc")
    summary = registry.summary()

    assert loaded is not None
    assert loaded.cache_key == "avatar:v1:abc"
    assert loaded.artifact_kind == "avatar"
    assert loaded.image_path == image_path
    assert loaded.metadata_path == metadata_path
    assert loaded.model == "black-forest-labs/flux-schnell"
    assert loaded.prompt_version == "avatar-body-profile-v4"
    assert loaded.size_bytes == len(b"avatar-image")
    assert loaded.metadata == {"garment_region": "upper_body"}
    assert summary["total_count"] == 1
    assert summary["total_size_bytes"] == len(b"avatar-image")
    assert summary["by_kind"]["avatar"]["count"] == 1
    assert summary["by_kind"]["avatar"]["size_bytes"] == len(b"avatar-image")


def test_cache_registry_marks_artifact_accessed(tmp_path: Path):
    image_path = tmp_path / "previews" / "avatar-preview-v1-abc.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"preview-image")
    registry = AvatarCacheRegistry(tmp_path / "cache_index.sqlite3")
    registry.upsert_artifact(
        CacheArtifactRecord(
            cache_key="avatar-preview:v1:abc",
            artifact_kind="preview",
            image_path=image_path,
            model="qwen/qwen-image-edit-2511",
            prompt_version="avatar-qwen-multimodal-preview-v1",
            input_mapping="multi_image_edit",
        )
    )
    before = registry.get_artifact("avatar-preview:v1:abc")

    registry.mark_accessed("avatar-preview:v1:abc")
    after = registry.get_artifact("avatar-preview:v1:abc")

    assert before is not None
    assert after is not None
    assert after.last_accessed_at >= before.last_accessed_at
