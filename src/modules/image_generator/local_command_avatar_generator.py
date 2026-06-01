"""
Local command based synthetic avatar generator.

This adapter lets the API call a user-managed local image generation command while
keeping the same avatar-generator interface as the Replicate implementation.
"""

from __future__ import annotations

import base64
import logging
import shlex
import subprocess
import threading
import time
import uuid
from pathlib import Path

from src.config.settings import get_settings
from src.modules.avatar_preview.prompt_builder import AVATAR_PROMPT_VERSION

logger = logging.getLogger(__name__)


class LocalCommandAvatarGenerator:
    """Generate a synthetic avatar by executing a configured local command."""

    DEFAULT_MODEL_ID = "local-command-avatar"
    DEFAULT_CATALOG_VERSION = "local-command-synthetic-person-photo-v1"

    def __init__(
        self,
        *,
        command_template: str | None = None,
        output_image_path: Path | None = None,
        output_dir: Path | None = None,
        model_id: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.command_template = (
            command_template
            if command_template is not None
            else settings.local_avatar_command
        )
        self.output_image_path = output_image_path
        self.output_dir = output_dir or settings.local_avatar_output_dir
        self.model_id = model_id or settings.local_avatar_model_id
        self.timeout_seconds = timeout_seconds or settings.local_avatar_timeout
        self.avatar_catalog_version = self.DEFAULT_CATALOG_VERSION

    def get_runtime_metadata(self) -> dict[str, str]:
        return {
            "avatar_model": self.model_id,
            "avatar_catalog_version": self.avatar_catalog_version,
            "avatar_prompt_version": AVATAR_PROMPT_VERSION,
        }

    def generate_avatar(self, *, prompt: str, size: str = "1024x1024") -> str:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Avatar generation prompt is empty")
        if not self.command_template.strip():
            raise ValueError("LOCAL_AVATAR_COMMAND is required for local avatar mode")

        output_path = self._next_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()

        command = self._build_command(
            prompt=normalized_prompt,
            output_path=output_path,
            size=size,
        )
        log_path = output_path.with_suffix(".log")
        logger.info(
            "Running local avatar command (model_id=%s, log_path=%s)",
            self.model_id,
            log_path,
        )
        returncode = self._run_command_streaming(
            command,
            log_path=log_path,
        )
        if returncode != 0:
            raise ValueError(
                f"Local avatar command failed with exit code {returncode}. "
                f"See log: {log_path}"
            )
        if not output_path.exists():
            raise ValueError(
                "Local avatar command did not create output image: "
                f"{output_path}. See log: {log_path}"
            )

        return base64.b64encode(output_path.read_bytes()).decode("utf-8")

    def _run_command_streaming(self, command: str, *, log_path: Path) -> int:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        start_time = time.monotonic()

        with log_path.open("w", encoding="utf-8") as log_file:

            def stream_output() -> None:
                if process.stdout is None:
                    return
                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()
                    logger.info("[local-avatar] %s", line.rstrip())

            reader_thread = threading.Thread(target=stream_output, daemon=True)
            reader_thread.start()

            while True:
                try:
                    returncode = process.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired as exc:
                    elapsed = time.monotonic() - start_time
                    if elapsed < self.timeout_seconds:
                        continue
                    process.kill()
                    reader_thread.join(timeout=1)
                    timeout_message = (
                        f"Local avatar command timed out after "
                        f"{self.timeout_seconds} seconds. See log: {log_path}\n"
                    )
                    log_file.write(timeout_message)
                    log_file.flush()
                    raise ValueError(timeout_message.strip()) from exc

            reader_thread.join(timeout=1)
            return returncode

    def _next_output_path(self) -> Path:
        if self.output_image_path is not None:
            return self.output_image_path
        return self.output_dir / f"local-avatar-{uuid.uuid4().hex}.png"

    def _build_command(self, *, prompt: str, output_path: Path, size: str) -> str:
        return self.command_template.format(
            prompt=shlex.quote(prompt),
            output_image=shlex.quote(str(output_path)),
            size=shlex.quote(size),
        )
