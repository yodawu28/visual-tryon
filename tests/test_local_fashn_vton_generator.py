import base64
import sys

import pytest

from src.modules.avatar_preview.profile import FashnVtonCategory
from src.modules.image_generator.local_fashn_vton_generator import (
    LocalFashnVtonGenerator,
)


def test_runtime_metadata_identifies_local_fashn_vton():
    generator = LocalFashnVtonGenerator(
        command_template="unused",
        model="fashn-test",
    )

    assert generator.get_runtime_metadata() == {
        "preview_model": "fashn-test",
        "preview_input_mapping": "local_fashn_vton",
        "preview_prompt_version": "fashn-vton-local-v1",
    }


def test_build_command_args_formats_expected_placeholders(tmp_path):
    generator = LocalFashnVtonGenerator(
        command_template=(
            "python infer.py --model_image {avatar_image} "
            "--garment_image {garment_image} --category {category} "
            "--output {output_image} --size {size}"
        ),
    )

    args = generator._build_command_args(
        avatar_image=tmp_path / "avatar.png",
        garment_image=tmp_path / "garment.png",
        output_image=tmp_path / "output.png",
        category=FashnVtonCategory.BOTTOMS,
        prompt="ignored",
        size="1024x1024",
    )

    assert args == [
        "python",
        "infer.py",
        "--model_image",
        str(tmp_path / "avatar.png"),
        "--garment_image",
        str(tmp_path / "garment.png"),
        "--category",
        "bottoms",
        "--output",
        str(tmp_path / "output.png"),
        "--size",
        "1024x1024",
    ]


@pytest.mark.skip(reason="Legacy subprocess test flakes in full suite with OMP SHM")
def test_generate_tryon_from_b64_runs_command_template(tmp_path):
    runner_path = tmp_path / "fake_fashn_runner.py"
    runner_path.write_text(
        "\n".join(
            [
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--avatar')",
                "parser.add_argument('--garment')",
                "parser.add_argument('--category')",
                "parser.add_argument('--output')",
                "args = parser.parse_args()",
                "Path(args.output).write_bytes(",
                "    args.category.encode() + b'|' +",
                "    Path(args.avatar).read_bytes() + b'|' +",
                "    Path(args.garment).read_bytes()",
                ")",
            ]
        ),
        encoding="utf-8",
    )
    generator = LocalFashnVtonGenerator(
        command_template=(
            f"{sys.executable} {runner_path} --avatar {{avatar_image}} "
            "--garment {garment_image} --category {category} "
            "--output {output_image}"
        ),
    )
    generator.set_case_context(fashn_category="bottoms")

    result = generator.generate_tryon_from_b64(
        base_image_b64=base64.b64encode(b"avatar-image").decode("utf-8"),
        garment_image_b64=base64.b64encode(b"garment-image").decode("utf-8"),
        inpainting_prompt="ignored",
    )

    assert base64.b64decode(result) == b"bottoms|avatar-image|garment-image"


def test_generate_tryon_requires_command_template():
    generator = LocalFashnVtonGenerator(command_template=None)

    with pytest.raises(ValueError, match="command template is required"):
        generator.generate_tryon(
            base_image=b"avatar",
            garment_image=b"garment",
            inpainting_prompt="ignored",
        )
