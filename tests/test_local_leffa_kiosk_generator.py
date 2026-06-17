import base64
import subprocess
from pathlib import Path

from src.modules.image_generator import local_leffa_kiosk_generator as leffa_module
from src.modules.image_generator.local_leffa_kiosk_generator import (
    LocalLeffaKioskGenerator,
)


def test_local_leffa_kiosk_generator_maps_tops_to_upper_body(monkeypatch, tmp_path):
    command = _run_fake_generation(monkeypatch, tmp_path, garment_category="tops")

    assert _command_value(command, "--garment-type") == "upper_body"
    assert _fake_condition_calls[-1]["person_framing"] == "upper_body"


def test_local_leffa_kiosk_generator_maps_bottoms_to_lower_body(monkeypatch, tmp_path):
    command = _run_fake_generation(monkeypatch, tmp_path, garment_category="bottoms")

    assert _command_value(command, "--garment-type") == "lower_body"
    assert _fake_condition_calls[-1]["person_framing"] == "full_body"


def test_local_leffa_kiosk_generator_maps_one_pieces_to_dresses(monkeypatch, tmp_path):
    command = _run_fake_generation(
        monkeypatch,
        tmp_path,
        garment_category="one_pieces",
    )

    assert _command_value(command, "--garment-type") == "dresses"
    assert _fake_condition_calls[-1]["person_framing"] == "full_body"


def test_local_leffa_kiosk_generator_maps_full_outfit_to_dresses(
    monkeypatch,
    tmp_path,
):
    command = _run_fake_generation(
        monkeypatch,
        tmp_path,
        garment_category="full_outfit",
    )

    assert _command_value(command, "--garment-type") == "dresses"
    assert _fake_condition_calls[-1]["person_framing"] == "full_body"


def test_local_leffa_kiosk_generator_rejects_unknown_category(monkeypatch, tmp_path):
    generator = _generator(tmp_path)

    try:
        generator.generate_kiosk_tryon(
            user_image=b"user-image",
            garment_image=b"garment-image",
            prompt="try on",
            garment_category="hats",
            garment_type=None,
            session_id="session",
            garment_id="garment",
            size="768x1024",
        )
    except ValueError as exc:
        assert "supports tops, bottoms, one_pieces" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown category")


_fake_condition_calls = []


def _run_fake_generation(monkeypatch, tmp_path, *, garment_category: str) -> list[str]:
    commands = []
    _fake_condition_calls.clear()

    def fake_score_inputs(*, person_image, garment_image, garment_category):
        return {
            "passed": True,
            "garment_category": garment_category,
            "recommendation": "ok",
        }

    def fake_condition_inputs(**kwargs):
        _fake_condition_calls.append(kwargs)
        Path(kwargs["person_output"]).write_bytes(b"person-conditioned")
        Path(kwargs["garment_output"]).write_bytes(b"garment-conditioned")
        Path(kwargs["report"]).write_text("{}", "utf-8")
        return {
            "success": True,
            "person": {"framing": kwargs["person_framing"]},
        }

    def fake_run(command, **kwargs):
        commands.append(command)
        output = Path(command[command.index("--output") + 1])
        report = Path(command[command.index("--report") + 1])
        output.write_bytes(b"leffa-output")
        report.write_text('{"success": true}', "utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(leffa_module, "_score_inputs", fake_score_inputs)
    monkeypatch.setattr(leffa_module, "_condition_inputs", fake_condition_inputs)
    monkeypatch.setattr(leffa_module.subprocess, "run", fake_run)

    result = _generator(tmp_path).generate_kiosk_tryon(
        user_image=b"user-image",
        garment_image=b"garment-image",
        prompt="try on",
        garment_category=garment_category,
        garment_type="test-garment",
        session_id="session",
        garment_id="garment",
        size="768x1024",
    )

    assert base64.b64decode(result) == b"leffa-output"
    assert len(commands) == 1
    return commands[0]


def _generator(tmp_path) -> LocalLeffaKioskGenerator:
    return LocalLeffaKioskGenerator(
        work_dir=tmp_path / "work",
        leffa_root=tmp_path / "Leffa",
        repo_url="https://example.com/Leffa.git",
        model_repo_id="fake/Leffa",
        checkpoint_dir=tmp_path / "ckpts",
        no_clone=True,
    )


def _command_value(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]
