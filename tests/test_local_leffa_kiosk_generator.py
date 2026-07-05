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


def test_local_leffa_kiosk_generator_uses_configured_python(
    monkeypatch,
    tmp_path,
):
    leffa_python = tmp_path / "venvs" / "leffa" / "bin" / "python"
    command = _run_fake_generation(
        monkeypatch,
        tmp_path,
        garment_category="tops",
        python_executable=leffa_python,
    )

    assert command[0] == str(leffa_python)


def test_local_leffa_kiosk_generator_streams_subprocess_output(monkeypatch, tmp_path):
    _run_fake_generation(monkeypatch, tmp_path, garment_category="tops")

    assert _fake_run_kwargs[-1]["capture_output"] is False


def test_local_leffa_kiosk_generator_calls_service_in_service_mode(
    monkeypatch,
    tmp_path,
):
    _fake_condition_calls.clear()
    _fake_run_kwargs.clear()
    http_calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

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

    def fail_subprocess_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in service mode")

    def fake_get(url, *, timeout):
        http_calls.append({"method": "GET", "url": url, "timeout": timeout})
        return FakeResponse({"ready": True})

    def fake_post(url, *, json, timeout):
        http_calls.append(
            {
                "method": "POST",
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        Path(json["output"]).write_bytes(b"leffa-service-output")
        Path(json["report"]).write_text('{"success": true, "mode": "service"}', "utf-8")
        return FakeResponse(
            {
                "success": True,
                "engine": "leffa",
                "output": json["output"],
                "report": json["report"],
                "service_marker": "fake-service",
            }
        )

    monkeypatch.setattr(leffa_module, "_score_inputs", fake_score_inputs)
    monkeypatch.setattr(leffa_module, "_condition_inputs", fake_condition_inputs)
    monkeypatch.setattr(leffa_module.subprocess, "run", fail_subprocess_run)
    monkeypatch.setattr(leffa_module.httpx, "get", fake_get)
    monkeypatch.setattr(leffa_module.httpx, "post", fake_post)

    generator = _generator(
        tmp_path,
        execution_mode="service",
        service_url="http://127.0.0.1:8091/",
    )

    result = generator.generate_kiosk_tryon(
        user_image=b"user-image",
        garment_image=b"garment-image",
        prompt="try on",
        garment_category="bottoms",
        garment_type="test-garment",
        session_id="session",
        garment_id="garment",
        size="768x1024",
    )

    assert base64.b64decode(result) == b"leffa-service-output"
    assert _fake_run_kwargs == []
    assert [call["method"] for call in http_calls] == ["GET", "POST"]
    assert http_calls[0]["url"] == "http://127.0.0.1:8091/ready"
    assert http_calls[1]["url"] == "http://127.0.0.1:8091/v1/generate"

    request_json = http_calls[1]["json"]
    assert request_json == {
        "engine": "leffa",
        "person_image": str(_fake_condition_calls[-1]["person_output"]),
        "garment_image": str(_fake_condition_calls[-1]["garment_output"]),
        "output": request_json["output"],
        "report": request_json["report"],
        "garment_type": "lower_body",
        "size": "768x1024",
        "steps": 30,
        "guidance_scale": 2.5,
        "seed": 42,
        "ref_acceleration": False,
        "repaint": False,
        "preprocess_garment": False,
    }
    assert Path(request_json["output"]).read_bytes() == b"leffa-service-output"
    assert Path(request_json["report"]).exists()

    metadata = generator.get_last_generation_metadata()
    assert metadata["execution_mode"] == "service"
    assert metadata["service"] == {
        "url": "http://127.0.0.1:8091",
        "response": {
            "success": True,
            "engine": "leffa",
            "output": request_json["output"],
            "report": request_json["report"],
            "service_marker": "fake-service",
        },
    }


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
_fake_run_kwargs = []


def _run_fake_generation(
    monkeypatch,
    tmp_path,
    *,
    garment_category: str,
    python_executable: Path | None = None,
) -> list[str]:
    commands = []
    _fake_condition_calls.clear()
    _fake_run_kwargs.clear()

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
        _fake_run_kwargs.append(kwargs)
        output = Path(command[command.index("--output") + 1])
        report = Path(command[command.index("--report") + 1])
        output.write_bytes(b"leffa-output")
        report.write_text('{"success": true}', "utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(leffa_module, "_score_inputs", fake_score_inputs)
    monkeypatch.setattr(leffa_module, "_condition_inputs", fake_condition_inputs)
    monkeypatch.setattr(leffa_module.subprocess, "run", fake_run)

    result = _generator(
        tmp_path, python_executable=python_executable
    ).generate_kiosk_tryon(
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


def _generator(
    tmp_path,
    *,
    python_executable: Path | None = None,
    execution_mode: str = "subprocess",
    service_url: str = "http://127.0.0.1:8091",
) -> LocalLeffaKioskGenerator:
    return LocalLeffaKioskGenerator(
        work_dir=tmp_path / "work",
        leffa_root=tmp_path / "Leffa",
        repo_url="https://example.com/Leffa.git",
        model_repo_id="fake/Leffa",
        checkpoint_dir=tmp_path / "ckpts",
        python_executable=python_executable,
        no_clone=True,
        execution_mode=execution_mode,
        service_url=service_url,
    )


def _command_value(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]
