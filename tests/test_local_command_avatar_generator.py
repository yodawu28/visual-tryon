import base64
import subprocess
import shlex

import pytest

from src.modules.image_generator.local_command_avatar_generator import (
    LocalCommandAvatarGenerator,
)


class FakePopen:
    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.stdout = iter(["loading model\n", "saving output\n"])
        self.returncode = 0
        self.killed = False

    def wait(self, timeout):
        self.timeout = timeout
        return self.returncode

    def kill(self):
        self.killed = True

    def communicate(self):
        return ("", "")


def test_generate_avatar_runs_command_template_and_returns_output_base64(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "avatar.png"
    calls = []

    def fake_popen(command, **kwargs):
        calls.append(
            {
                "command": command,
                **kwargs,
            }
        )
        output_path.write_bytes(b"local-avatar")
        return FakePopen(command, **kwargs)

    monkeypatch.setattr(
        "src.modules.image_generator.local_command_avatar_generator.subprocess.Popen",
        fake_popen,
    )
    generator = LocalCommandAvatarGenerator(
        command_template=(
            "avatar-cli --prompt {prompt} --output {output_image} --size {size}"
        ),
        output_image_path=output_path,
        model_id="local-flux-schnell",
        timeout_seconds=12,
    )

    avatar = generator.generate_avatar(
        prompt="synthetic avatar, athletic build",
        size="1024x1024",
    )

    assert avatar == base64.b64encode(b"local-avatar").decode("utf-8")
    assert calls == [
        {
            "command": (
                "avatar-cli --prompt 'synthetic avatar, athletic build' "
                f"--output {shlex.quote(str(output_path))} --size 1024x1024"
            ),
            "shell": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
        }
    ]
    log_path = output_path.with_suffix(".log")
    assert log_path.read_text(encoding="utf-8") == "loading model\nsaving output\n"


def test_generate_avatar_requires_non_empty_command_template(tmp_path):
    generator = LocalCommandAvatarGenerator(
        command_template=" ",
        output_image_path=tmp_path / "avatar.png",
    )

    with pytest.raises(ValueError, match="LOCAL_AVATAR_COMMAND is required"):
        generator.generate_avatar(prompt="synthetic avatar")


def test_generate_avatar_raises_when_command_does_not_write_output(
    tmp_path, monkeypatch
):
    def fake_popen(command, **kwargs):
        return FakePopen(command, **kwargs)

    monkeypatch.setattr(
        "src.modules.image_generator.local_command_avatar_generator.subprocess.Popen",
        fake_popen,
    )
    generator = LocalCommandAvatarGenerator(
        command_template="avatar-cli --output {output_image}",
        output_image_path=tmp_path / "missing.png",
    )

    with pytest.raises(ValueError, match="did not create output image"):
        generator.generate_avatar(prompt="synthetic avatar")


def test_generate_avatar_timeout_is_wrapped_with_log_path(tmp_path, monkeypatch):
    output_path = tmp_path / "avatar.png"

    class TimeoutPopen(FakePopen):
        def wait(self, timeout):
            raise subprocess.TimeoutExpired(cmd=self.command, timeout=timeout)

    process = None

    def fake_popen(command, **kwargs):
        nonlocal process
        process = TimeoutPopen(command, **kwargs)
        return process

    monkeypatch.setattr(
        "src.modules.image_generator.local_command_avatar_generator.subprocess.Popen",
        fake_popen,
    )
    generator = LocalCommandAvatarGenerator(
        command_template="avatar-cli --output {output_image}",
        output_image_path=output_path,
        timeout_seconds=12,
    )

    with pytest.raises(ValueError, match="timed out after 12 seconds"):
        generator.generate_avatar(prompt="synthetic avatar")

    assert process is not None
    assert process.killed is True
    assert str(output_path.with_suffix(".log")) in output_path.with_suffix(
        ".log"
    ).read_text(encoding="utf-8")


def test_get_runtime_metadata_returns_local_avatar_identity(tmp_path):
    generator = LocalCommandAvatarGenerator(
        command_template="avatar-cli --output {output_image}",
        output_image_path=tmp_path / "avatar.png",
        model_id="local-avatar-v1",
    )

    assert generator.get_runtime_metadata() == {
        "avatar_model": "local-avatar-v1",
        "avatar_catalog_version": "local-command-synthetic-person-photo-v1",
        "avatar_prompt_version": "avatar-body-profile-v4",
    }
