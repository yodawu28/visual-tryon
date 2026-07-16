from pathlib import Path
from types import SimpleNamespace

import scripts.run_kiosk_worker as run_kiosk_worker
from src.api.routes import kiosk_tryon


def test_api_local_leffa_builder_passes_advanced_controls(monkeypatch, tmp_path):
    captured = []

    class FakeLocalLeffaKioskGenerator:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    monkeypatch.setattr(
        kiosk_tryon,
        "LocalLeffaKioskGenerator",
        FakeLocalLeffaKioskGenerator,
    )

    generator = kiosk_tryon._build_kiosk_visual_generator(_settings(tmp_path))

    assert isinstance(generator, FakeLocalLeffaKioskGenerator)
    assert captured[0]["ref_acceleration"] is True
    assert captured[0]["repaint"] is True
    assert captured[0]["preprocess_garment"] is True


def test_worker_local_leffa_builder_passes_advanced_controls(monkeypatch, tmp_path):
    captured = []

    class FakeLocalLeffaKioskGenerator:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    monkeypatch.setattr(
        run_kiosk_worker,
        "LocalLeffaKioskGenerator",
        FakeLocalLeffaKioskGenerator,
    )

    generator = run_kiosk_worker._build_kiosk_visual_generator(_settings(tmp_path))

    assert isinstance(generator, FakeLocalLeffaKioskGenerator)
    assert captured[0]["ref_acceleration"] is True
    assert captured[0]["repaint"] is True
    assert captured[0]["preprocess_garment"] is True


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        kiosk_visual_preview_provider="local_leffa",
        temp_storage_dir=tmp_path / "data",
        local_leffa_root=tmp_path / "models" / "Leffa",
        local_leffa_repo_url="https://example.test/Leffa.git",
        local_leffa_model_repo_id="example/Leffa",
        local_leffa_checkpoint_dir=tmp_path / "models" / "Leffa" / "ckpts",
        local_leffa_python=None,
        local_leffa_hf_home=None,
        local_leffa_torch_home=None,
        local_leffa_xdg_cache_home=None,
        local_leffa_no_clone=True,
        local_leffa_size="768x1024",
        local_leffa_device="cuda",
        local_leffa_dtype="float16",
        local_leffa_vt_model_type="viton_hd",
        local_leffa_steps=30,
        local_leffa_guidance_scale=2.5,
        local_leffa_seed=42,
        local_leffa_timeout=900,
        local_leffa_ref_acceleration=True,
        local_leffa_repaint=True,
        local_leffa_preprocess_garment=True,
        local_visual_engine_mode="subprocess",
        local_visual_engine_service_url="http://127.0.0.1:8091",
        local_visual_engine_service_ready_timeout=900,
        effective_local_visual_engine_service_request_timeout=900,
    )
