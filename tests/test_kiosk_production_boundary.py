from pathlib import Path
from types import SimpleNamespace


def test_kiosk_requirements_do_not_install_experimental_backends():
    requirements = Path("requirements-kiosk.txt").read_text("utf-8")
    constraints = Path("constraints-kiosk.txt").read_text("utf-8")
    combined = f"{requirements}\n{constraints}"

    assert "insightface" not in combined
    assert "onnxruntime" not in combined
    assert "replicate" not in combined


def test_runpod_template_uses_kiosk_production_model_boundary():
    template = Path(".env.runpod.example").read_text("utf-8")
    makefile = Path("Makefile").read_text("utf-8")
    settings = Path("src/config/settings.py").read_text("utf-8")

    assert "LOCAL_LEFFA_REPAINT=true" in template
    assert "LOCAL_LEFFA_PREPROCESS_GARMENT=true" in template
    assert "replicate_qwen" not in template
    assert "replicate_qwen" not in settings
    assert "REPLICATE_PREVIEW_MODEL" not in template
    assert "INSIGHTFACE" not in template
    assert "insightface" not in makefile


def test_runpod_makefile_exposes_only_leffa_visual_engine_surface():
    makefile = Path("Makefile").read_text("utf-8")

    for removed_surface in (
        "runpod-qwen-edit-smoke",
        "runpod-install-qwen-edit-deps",
        "runpod-catvton",
        "runpod-install-catvton",
        "runpod-omnivton",
        "runpod-install-omnivton",
        "RUNPOD_QWEN_EDIT",
        "RUNPOD_CATVTON",
        "RUNPOD_OMNIVTON",
    ):
        assert removed_surface not in makefile

    assert "runpod-leffa-smoke" in makefile
    assert "runpod-install-leffa-deps" in makefile


def test_kiosk_router_does_not_import_replicate_provider_at_module_load():
    source = Path("src/api/routes/kiosk_tryon.py").read_text("utf-8")

    assert "replicate_avatar_preview_generator import" not in source
    assert "ReplicateAvatarPreviewGenerator()" not in source
    assert "_build_replicate_qwen_generator" not in source
    assert "replicate_qwen" not in source


def test_kiosk_worker_does_not_import_replicate_provider_at_module_load():
    source = Path("scripts/run_kiosk_worker.py").read_text("utf-8")

    assert "replicate_avatar_preview_generator import" not in source
    assert "ReplicateAvatarPreviewGenerator()" not in source
    assert "replicate_qwen" not in source


def test_kiosk_profile_does_not_warm_up_legacy_privacy_face_detector():
    from src.main import should_warm_up_face_detector

    assert should_warm_up_face_detector(SimpleNamespace(api_profile="kiosk")) is False
    assert should_warm_up_face_detector(SimpleNamespace(api_profile="full")) is True
