from pathlib import Path

import pytest

from scripts import local_leffa_smoke


def _create_fake_leffa_assets(ckpt_dir: Path) -> None:
    (ckpt_dir / "stable-diffusion-inpainting").mkdir(parents=True)
    (ckpt_dir / "virtual_tryon.pth").write_bytes(b"fake")
    (ckpt_dir / "virtual_tryon_dc.pth").write_bytes(b"fake")
    (ckpt_dir / "densepose").mkdir()
    (ckpt_dir / "densepose" / "densepose_rcnn_R_50_FPN_s1x.yaml").write_text(
        "fake",
        encoding="utf-8",
    )
    (ckpt_dir / "densepose" / "model_final_162be9.pkl").write_bytes(b"fake")
    (ckpt_dir / "humanparsing").mkdir()
    (ckpt_dir / "humanparsing" / "parsing_atr.onnx").write_bytes(b"fake")
    (ckpt_dir / "humanparsing" / "parsing_lip.onnx").write_bytes(b"fake")
    (ckpt_dir / "openpose").mkdir()
    (ckpt_dir / "openpose" / "body_pose_model.pth").write_bytes(b"fake")


def test_parse_args_supports_download_checkpoints_only_without_images(tmp_path):
    args = local_leffa_smoke.parse_args(
        [
            "--download-checkpoints-only",
            "--report",
            str(tmp_path / "preload.json"),
            "--leffa-root",
            str(tmp_path / "Leffa"),
        ]
    )

    assert args.download_checkpoints_only is True
    assert args.person_image is None
    assert args.garment_image is None
    assert args.output is None


def test_parse_args_requires_images_for_full_generation(tmp_path):
    with pytest.raises(SystemExit):
        local_leffa_smoke.parse_args(
            [
                "--leffa-root",
                str(tmp_path / "Leffa"),
                "--output",
                str(tmp_path / "out.png"),
            ]
        )


def test_generate_smoke_can_preload_checkpoints_without_inputs(
    monkeypatch,
    tmp_path,
):
    leffa_root = tmp_path / "Leffa"
    ckpt_dir = tmp_path / "ckpts"
    report = tmp_path / "preload.json"
    downloaded: list[tuple[str, str]] = []

    def fake_snapshot_download(*, repo_id: str, local_dir: str) -> None:
        downloaded.append((repo_id, local_dir))
        _create_fake_leffa_assets(Path(local_dir))

    monkeypatch.setattr(local_leffa_smoke, "ensure_leffa_repo", lambda **_: None)
    monkeypatch.setattr(
        local_leffa_smoke,
        "load_leffa_modules",
        lambda _: {"snapshot_download": fake_snapshot_download},
    )

    result = local_leffa_smoke.generate_smoke(
        person_image=None,
        garment_image=None,
        output=None,
        report=report,
        leffa_root=leffa_root,
        repo_url="https://example.com/Leffa.git",
        no_clone=False,
        model_repo_id="fake/Leffa",
        checkpoint_dir=ckpt_dir,
        size="768x1024",
        device="cpu",
        dtype="float16",
        vt_model_type="viton_hd",
        garment_type="upper_body",
        steps=30,
        guidance_scale=2.5,
        seed=42,
        ref_acceleration=False,
        repaint=False,
        preprocess_garment=False,
        allow_tf32=True,
        download_checkpoints_only=True,
    )

    assert downloaded == [("fake/Leffa", str(ckpt_dir))]
    assert result["success"] is True
    assert result["download_checkpoints_only"] is True
    assert result["checkpoint_assets"]["virtual_tryon_checkpoint"] == str(
        ckpt_dir / "virtual_tryon.pth"
    )
    assert report.exists()


def test_generate_smoke_validates_inputs_before_checkpoint_download(
    monkeypatch,
    tmp_path,
):
    def fake_snapshot_download(*, repo_id: str, local_dir: str) -> None:
        raise AssertionError("checkpoint download should not start for missing inputs")

    monkeypatch.setattr(local_leffa_smoke, "ensure_leffa_repo", lambda **_: None)
    monkeypatch.setattr(
        local_leffa_smoke,
        "load_leffa_modules",
        lambda _: {"snapshot_download": fake_snapshot_download},
    )

    try:
        local_leffa_smoke.generate_smoke(
            person_image=tmp_path / "missing-person.png",
            garment_image=tmp_path / "missing-garment.png",
            output=tmp_path / "output.png",
            report=tmp_path / "report.json",
            leffa_root=tmp_path / "Leffa",
            repo_url="https://example.com/Leffa.git",
            no_clone=False,
            model_repo_id="fake/Leffa",
            checkpoint_dir=tmp_path / "ckpts",
            size="768x1024",
            device="cpu",
            dtype="float16",
            vt_model_type="viton_hd",
            garment_type="upper_body",
            steps=30,
            guidance_scale=2.5,
            seed=42,
            ref_acceleration=False,
            repaint=False,
            preprocess_garment=False,
            allow_tf32=True,
        )
    except FileNotFoundError as exc:
        assert "Missing person image" in str(exc)
    else:
        raise AssertionError(
            "Expected missing input to fail before checkpoint download"
        )
